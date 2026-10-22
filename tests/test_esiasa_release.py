"""M7 release pin: the eSiasa demo archive verifies and regenerates cleanly.

The committed demo bundle/exports under ``demos/esiasa/`` are the external
verification deliverable. This test verifies the archive itself, then
regenerates from the fixed demo seeds and pins the record layer:

- every non-``Signature`` artifact (question, ledger, panel, protocol
  params, personae, turns, telemetry, round, summary, verdict, manifests,
  certificates, key publications, tree heads) reproduces byte-identically;
- ``Signature`` artifacts are fresh-but-equivalent per run (FIPS 204
  hedged signing — the `cryptography` backend offers no deterministic
  sign knob), so cids, manifests, and verdict CIDs that embed them
  legitimately differ run to run;
- the committed exports re-render byte-identically from the committed
  bundle, modulo the environment-dependent verification-QR region (the
  archive was rendered with the optional ``qrcode`` extra installed; a
  fresh render without it omits exactly the ``<div class="qr">`` region —
  the markdown and JSON-LD records are extra-free and byte-identical
  everywhere);
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

from conclave_core.verifier import verify_bundle  # noqa: E402

DEMO = ROOT / "demos" / "esiasa"


def _regenerate() -> Path:
    """Run the demo generator into a fresh temp dir; return its root."""

    staging = tempfile.mkdtemp(prefix="esiasa-regen-")
    # the generator anchors its defaults at the repo; --out redirects both
    # bundle and exports, and the ledger/roster reads stay at the repo paths
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_esiasa_demo.py"),
         "--out", staging],
        capture_output=True, text=True, timeout=300, cwd=str(ROOT),
    )
    if result.returncode != 0:
        raise AssertionError(f"demo regeneration failed: {result.stdout}\n{result.stderr}")
    return Path(staging)


def _without_qr_region(html: bytes) -> bytes:
    """Drop the environment-dependent ``<div class="qr">…</div>`` line."""

    import re

    return re.sub(rb'\n<div class="qr">.*?</div>', b"", html, flags=re.DOTALL)


class EsiasaReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.regen = _regenerate()

    @staticmethod
    def _decode_bundle(bundle_dir: Path) -> dict[str, tuple[str, bytes]]:
        """Map cid -> (artifact type, canonical bytes) for one bundle."""

        from conclave_core.cbor import decode

        decoded: dict[str, tuple[str, bytes]] = {}
        for path in sorted(Path(bundle_dir / "artifacts").glob("*.cbor")):
            raw = path.read_bytes()
            decoded[path.stem] = (decode(raw)["type"], raw)
        return decoded

    def test_committed_bundle_verifies_standalone(self):
        problems, _summary = verify_bundle(DEMO / "bundle")
        self.assertEqual(problems, [])

    def test_regen_bundle_verifies_shape(self):
        problems, summary = verify_bundle(self.regen / "bundle")
        self.assertEqual(problems, [], summary)

    def test_regen_preserves_the_non_signature_record(self):
        committed = self._decode_bundle(DEMO / "bundle")
        regenerated = self._decode_bundle(self.regen / "bundle")
        self.assertEqual(len(committed), len(regenerated))

        from collections import Counter

        self.assertEqual(
            Counter(kind for kind, _raw in committed.values()),
            Counter(kind for kind, _raw in regenerated.values()),
            "artifact type counts must match across regenerations",
        )
        for cid, (kind, raw) in committed.items():
            if kind == "Signature":
                continue  # hedged bytes: fresh-but-equivalent each run
            self.assertIn(cid, regenerated, f"{kind} cid drifted: {cid}")
            self.assertEqual(
                raw, regenerated[cid][1], f"{kind} artifact bytes drifted: {cid}"
            )

    def test_regen_exports_match_committed_exports(self):
        for name in ("decision-record.md", "decision-record.jsonld"):
            committed = (DEMO / "exports" / name).read_bytes()
            regenerated = (self.regen / "exports" / name).read_bytes()
            self.assertEqual(committed, regenerated, name)

        # The HTML carries the verification QR only where the optional
        # `qrcode` extra is importable; committed exports were rendered
        # with it. Byte-compare in full where the extras match, and
        # otherwise compare with exactly the QR region removed from both.
        committed = (DEMO / "exports" / "decision-record.html").read_bytes()
        regenerated = (self.regen / "exports" / "decision-record.html").read_bytes()
        try:
            import qrcode  # noqa: F401  (optional extra, mirrors verdict_export)
        except ImportError:
            self.assertEqual(
                _without_qr_region(committed),
                _without_qr_region(regenerated),
                "decision-record.html (QR region stripped)",
            )
        else:
            self.assertEqual(committed, regenerated, "decision-record.html")

    def test_demo_keystore_seeds_are_committed_and_live(self):
        for name in ("identity.seed", "registry.seed"):
            path = DEMO / "keys" / name
            self.assertTrue(path.is_file(), name)
            self.assertEqual(len(path.read_bytes()), 32, name)


if __name__ == "__main__":
    unittest.main()
