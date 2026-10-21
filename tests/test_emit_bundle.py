"""End-to-end M3 tests: run the emitter, verify bundles with the M2 verifier."""

from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from conclave_core.keystore import load_or_create_seed
from conclave_core.verifier import verify_bundle
from scripts.artifact_emitter import CaseSeed, emit_case_bundle

ROSTER = {
    "version": "0.1.0",
    "marshall": "conclave-marshall",
    "seats": [
        {
            "id": "conclave-feynman",
            "display_name": "Richard Feynman",
            "tier": "General",
            "type": "advocate",
            "lens": "Decompose until the mechanism is obvious",
            "model": "sonnet",
            "path": "agents/conclave-feynman.md",
        },
        {
            "id": "conclave-zhukov",
            "display_name": "Georgy Zhukov",
            "tier": "General",
            "type": "advocate",
            "lens": "Decisive force, initiative, operational reach",
            "model": "sonnet",
            "path": "agents/conclave-zhukov.md",
        },
        {
            "id": "conclave-marshall",
            "display_name": "Marshall",
            "tier": "Justice (always)",
            "type": "verifier",
            "lens": "Verification and directive compliance",
            "model": "opus",
            "path": "agents/conclave-marshall.md",
        },
    ],
}

LEDGER_ENTRIES = [
    {
        "id": "E1",
        "item": "Note: the staging cluster sustained the fixture load.",
        "source_type": "user_assertion",
        "source": "--evidence-note",
        "provenance": "User-supplied note at runner invocation",
        "handling": "Treat only as asserted input.",
    },
]

TRANSCRIPT = [
    {
        "seat": "conclave-feynman",
        "role": "round1",
        "slot": "sonnet",
        "provider": "anthropic",
        "model_family": "sonnet",
        "prompt_chars": 42,
        "ok": True,
        "prompt": "Round 1 prompt for feynman.",
        "response": "Feynman position text.",
    },
    {
        "seat": "conclave-zhukov",
        "role": "round1",
        "slot": "sonnet",
        "provider": "anthropic",
        "model_family": "sonnet",
        "prompt_chars": 42,
        "ok": True,
        "prompt": "Round 1 prompt for zhukov.",
        "response": "Zhukov position text.",
    },
    {
        "seat": "conclave-marshall",
        "role": "verification",
        "slot": "opus",
        "provider": "anthropic",
        "model_family": "opus",
        "prompt_chars": 44,
        "ok": True,
        "prompt": "Verification prompt for the marshall.",
        "response": "Verification result text.",
    },
]


def _case(tmp: Path, transcript: list[dict] | None) -> tuple[CaseSeed, Path, Path]:
    bundle_dir = tmp / "bundle"
    keys_dir = tmp / "keys"
    seed = CaseSeed(
        profile_id="architecture",
        problem="Should we split the analytics service?",
        timestamp="2026-10-21T09:00:00Z",
        seats=["conclave-feynman", "conclave-zhukov"],
        marshall_id="conclave-marshall",
        roster=ROSTER,
        ledger_entries=LEDGER_ENTRIES,
        transcript=transcript,
    )
    return seed, bundle_dir, keys_dir


class TestOpeningBundle(unittest.TestCase):
    """Scaffold (offline) run: an opening case with an empty log."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_opening_case_verifies_end_to_end(self) -> None:
        seed, bundle_dir, keys_dir = _case(self.tmp, None)
        emitted_dir, identity_fingerprint = emit_case_bundle(seed, bundle_dir, keys_dir)
        problems, summary = verify_bundle(emitted_dir)
        self.assertEqual(problems, [], msg="\n".join(problems))
        self.assertEqual(summary["status"], "VERIFIED")
        config = json.loads((emitted_dir / "bundle.json").read_text(encoding="utf-8"))
        self.assertEqual(config["expectedIdentityFingerprint"], identity_fingerprint)
        self.assertEqual(config["log"]["leaves"], [])

    def test_bundle_is_repeatable_and_stable_in_dag(self) -> None:
        seed, base_dir, keys_dir = _case(self.tmp, None)
        first_dir, first_fingerprint = emit_case_bundle(seed, base_dir / "a", keys_dir)
        second_dir, second_fingerprint = emit_case_bundle(seed, base_dir / "b", keys_dir)
        self.assertEqual(first_fingerprint, second_fingerprint)
        # deterministic key + deterministic DAG content question/ledger/panel:
        first_config = json.loads((first_dir / "bundle.json").read_text())
        second_config = json.loads((second_dir / "bundle.json").read_text())
        self.assertEqual(
            first_config["expectedRegistryFingerprint"],
            second_config["expectedRegistryFingerprint"],
        )


class TestProviderBundle(unittest.TestCase):
    """Provider run: turns recorded as artifacts from the transcript."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_provider_case_verifies_end_to_end(self) -> None:
        seed, bundle_dir, keys_dir = _case(self.tmp, TRANSCRIPT)
        emitted_dir, _ = emit_case_bundle(seed, bundle_dir, keys_dir)
        problems, summary = verify_bundle(emitted_dir)
        self.assertEqual(problems, [], msg="\n".join(problems))
        self.assertEqual(summary["status"], "VERIFIED")
        counts = summary["artifactCounts"]
        # round1 x2 advocates + the marshall verification call = 3 turns
        self.assertEqual(counts.get("Turn"), 3)
        self.assertEqual(counts.get("Round"), 1)

    def test_turn_raw_bytes_match_their_cids(self) -> None:
        seed, bundle_dir, keys_dir = _case(self.tmp, TRANSCRIPT)
        emitted_dir, _ = emit_case_bundle(seed, bundle_dir, keys_dir)
        from conclave_core.cbor import decode
        from conclave_core.artifacts import raw_cid

        artifacts_dir = emitted_dir / "artifacts"
        turns = []
        for path in sorted(artifacts_dir.glob("*.cbor")):
            artifact = decode(path.read_bytes())
            if artifact.get("type") == "Turn":
                turns.append(artifact)
        self.assertEqual(len(turns), 3)
        for turn in turns:
            prompt_bytes = (artifacts_dir / f"{turn['inputContextHash']}.raw").read_bytes()
            output_bytes = (artifacts_dir / f"{turn['output']}.raw").read_bytes()
            self.assertEqual(raw_cid(prompt_bytes), turn["inputContextHash"])
            self.assertEqual(raw_cid(output_bytes), turn["output"])


class TestKeystore(unittest.TestCase):
    def test_seed_created_once_with_owner_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keys" / "identity.seed"
            first = load_or_create_seed(path)
            second = load_or_create_seed(path)
            self.assertEqual(first, second)
            self.assertEqual(len(first), 32)
            mode = stat.S_IMODE(path.stat().st_mode)
            self.assertEqual(mode & 0o077, 0)  # no group/other access


if __name__ == "__main__":
    unittest.main()
