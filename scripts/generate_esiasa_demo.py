"""Regenerate the eSiasa M7 release demo (demos/esiasa/).

One real eSiasa policy question run end to end through the v0.2 machine
pipeline: frozen ledger → conclave convene → deterministic standing-voice
deliberation (M6 server orchestrator; provider seats remain operator-side)
→ model-verified case bundle → civic decision record exports.

The demo's logical record is stable: fixed demo keystore seeds (public by
design, disclosed in the demo README) and a fixed per-case orchestrator
seed make every non-signature artifact CID-identical across regenerations.
ML-DSA signing is hedged (FIPS 204 §5.4), so ``Signature`` artifacts carry
fresh-but-equivalent bytes each run and the manifest/verdict CIDs that
embed them differ; a regenerated bundle is an equally valid fresh witness
of the same record, and the committed ``bundle/`` + ``exports/`` pair is
the release archive that external parties verify.

Usage::

    python3 scripts/generate_esiasa_demo.py [--out demos/esiasa]

After regenerating, ``tests/test_esiasa_release.py`` checks the committed
archive and ``scripts/verdict_export.py`` (or the generator) re-exports
from it. Bundle reproducibility of the record layer depends on the repo's
artifact codecs; re-check after upgrades.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

from conclave_server.http import SeatlessClient  # noqa: E402
from conclave_server.materialize import materialize_case  # noqa: E402
from conclave_server.orchestrator import CaseRun, ConveneRequest  # noqa: E402
from conclave_server.sessions import SessionHub  # noqa: E402
from conclave_server.store import ArtifactStore  # noqa: E402
from scripts.verdict_export import DEFAULT_VERIFY_ENDPOINT, export_all  # noqa: E402

LEDGER_PATH = ROOT / "demos" / "esiasa" / "feeder-road-performance-contract.ledger.json"
ROSTER_PATH = ROOT / "configs" / "conclave-roster.json"

TIMESTAMP = "2026-10-21T07:30:00Z"
CASE_PROFILE = "esiasa-civic-stress"
# demo identity keys are public by design (demo README); the per-case
# orchestrator seed below is what makes the emitted bundle byte-stable
ORCHESTRATOR_SEED = bytes.fromhex(
    "3f9141c2aeb742d99d0cf43e77a19062b01965af5c22e3ad6791e8cdd2404a17"
)

# committed demo keystore seeds (identity, registry) — public by design;
# production installs generate theirs out of band (conclave_core.keystore)
IDENTITY_SEED = bytes.fromhex(
    "a4c11de39b57f0682ce71d9a44e0b83f18dd5c9e60b47f2ce3318da90a67b8c5"
)
REGISTRY_SEED = bytes.fromhex(
    "c83b5a9f772d4061b9e0c3f685147ad02e91fc4bb06a37d1e5c829447d3aaef2"
)


def _write_fixed_seeds(keys_dir: Path) -> None:
    """Install the public demo seeds with production file modes."""

    for name, seed in (("identity.seed", IDENTITY_SEED), ("registry.seed", REGISTRY_SEED)):
        path = keys_dir / name
        path.write_bytes(seed)
        os.chmod(path, 0o600)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_esiasa_demo",
        description="Regenerate the M7 eSiasa release demo bundle + exports.",
    )
    parser.add_argument("--out", default=str(ROOT / "demos" / "esiasa"))
    args = parser.parse_args(argv)
    out = Path(args.out)

    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    config = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    profiles = {profile["id"]: profile for profile in config["profiles"]}
    drafts = [
        {
            "item": entry["item"],
            "source": entry["source"],
            "source_type": entry["source_type"],
            "handling": entry["handling"],
            "sensitivity": entry["sensitivity"],
        }
        for entry in ledger["entries"]
    ]

    keys_dir = out / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    _write_fixed_seeds(keys_dir)

    db_path = out / "store.sqlite3"
    if db_path.exists():
        db_path.unlink()
    store = ArtifactStore(db_path)
    hub = SessionHub()
    request = ConveneRequest(
        profile_id=CASE_PROFILE,
        problem=ledger["decision"],
        roster={"version": config["version"], "seats": config["seats"]},
        seats=list(profiles[CASE_PROFILE]["seats"]),
        marshall_id=config["marshall"],
        ledger_entries=drafts,
        token_budget=None,
        protocol_params=None,
        timestamp=TIMESTAMP,
    )
    run = CaseRun(
        store, hub, keys_dir, SeatlessClient(), orchestrator_seed=ORCHESTRATOR_SEED
    )
    case_ref = run.convene(request)
    run.drive()
    hub_state = hub.state(case_ref)
    if hub_state is None or not hub_state.terminal:
        store.close()
        raise SystemExit(f"demo case did not terminate (phase {hub_state})")

    bundle = materialize_case(store, keys_dir, case_ref, out / "bundle")
    exports = export_all(
        bundle, out / "exports", ["adr", "jsonld", "html"], DEFAULT_VERIFY_ENDPOINT
    )

    from conclave_core.verifier import verify_bundle

    problems, summary = verify_bundle(bundle)
    store.close()

    print(f"case: {case_ref}")
    print(f"bundle: {bundle}")
    for path in exports:
        print(f"export: {path}")
    print(f"verifier problems: {problems}")
    print(f"summary: {summary}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
