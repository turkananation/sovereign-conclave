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
        "role": "round",
        "round": 0,
        "roundKind": "opening",
        "slot": "sonnet",
        "provider": "anthropic",
        "model_family": "sonnet",
        "prompt_chars": 42,
        "prompt_parts": {"static": 900, "dynamic": 60, "suffix": 40},
        "batch": False,
        "ok": True,
        "prompt": "Round 1 prompt for feynman.",
        "response": "Feynman position text.",
        "usage": {"inputTokens": 1200, "outputTokens": 280, "cacheReadTokens": 900, "cacheWriteTokens": 300},
        "usageEstimated": False,
        "elapsed_s": 0.4,
    },
    {
        "seat": "conclave-zhukov",
        "role": "round",
        "round": 0,
        "roundKind": "opening",
        "slot": "sonnet",
        "provider": "anthropic",
        "model_family": "sonnet",
        "prompt_chars": 42,
        "prompt_parts": {"static": 900, "dynamic": 60, "suffix": 40},
        "batch": False,
        "ok": True,
        "prompt": "Round 1 prompt for zhukov.",
        "response": "Zhukov position text.",
        "usage": {"inputTokens": 60, "outputTokens": 280, "cacheReadTokens": 1200, "cacheWriteTokens": 0},
        "usageEstimated": False,
        "elapsed_s": 0.3,
    },
    {
        "seat": "mechanical",
        "role": "distill",
        "round": 0,
        "roundKind": "mechanical:distill",
        "slot": "fast",
        "provider": "provider-alpha",
        "model_family": "fast-general",
        "prompt_chars": 80,
        "prompt_parts": {"static": 900, "dynamic": 60, "suffix": 40},
        "batch": True,
        "ok": True,
        "prompt": "Distiller prompt.",
        "response": (
            '{"summaryText": "Feynman wants a flagged split; Zhukov resists on readiness.",'
            ' "positions": ['
            '{"seatId": "conclave-feynman", "stance": "Split behind a flag", "citations": ["E1"]},'
            '{"seatId": "conclave-zhukov", "stance": "Hold the monolith", "citations": ["E1"]}],'
            ' "openDisagreements": ["feynman vs zhukov: pace of extraction"]}'
        ),
        "prompt_parts": {"static": 900, "dynamic": 60, "suffix": 40},
        "usageEstimated": True,
        "elapsed_s": 0.4,
    },
    {
        "seat": "conclave-marshall",
        "role": "verification",
        "round": 0,
        "roundKind": "opening",
        "slot": "opus",
        "provider": "anthropic",
        "model_family": "opus",
        "prompt_chars": 44,
        "prompt_parts": {"static": 900, "dynamic": 60, "suffix": 40},
        "batch": False,
        "ok": True,
        "prompt": "Verification prompt for the marshall.",
        "response": "Verification result text.",
        "usage": {"inputTokens": 90, "outputTokens": 300, "cacheReadTokens": 1260, "cacheWriteTokens": 0},
        "usageEstimated": False,
        "elapsed_s": 0.5,
    },
]

CONSENSUS_RECORD = {
    "seat": "mechanical",
    "role": "consensus",
    "round": 0,
    "roundKind": "mechanical:consensus",
    "slot": "fast",
    "provider": "provider-alpha",
    "model_family": "fast-general",
    "prompt_parts": {"static": 900, "dynamic": 60, "suffix": 40},
    "batch": False,
    "ok": True,
    "prompt": "Consensus prompt.",
    "response": '{"consensusScore": 87, "activeDissent": []}',
    "usageEstimated": True,
    "elapsed_s": 0.2,
}


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
        # 2 advocate openings + the mechanical distill + the marshall verification
        self.assertEqual(counts.get("Turn"), 3)
        self.assertEqual(counts.get("Round"), 1)
        self.assertEqual(counts.get("Summary"), 1)
        self.assertEqual(counts.get("Telemetry"), 4)

    def test_summary_binds_its_source_turns(self) -> None:
        seed, bundle_dir, keys_dir = _case(self.tmp, TRANSCRIPT)
        emitted_dir, _ = emit_case_bundle(seed, bundle_dir, keys_dir)
        from conclave_core.cbor import decode
        from conclave_core.artifacts import artifact_cid

        artifacts = [decode(p.read_bytes()) for p in sorted((emitted_dir / "artifacts").glob("*.cbor"))]
        summary = next(a for a in artifacts if a.get("type") == "Summary")
        turns = [artifact_cid(t) for t in artifacts if t.get("type") == "Turn" and t["roundIndex"] == 0
                 and t["seatId"] != "conclave-marshall"]
        # the mechanical record opens with static+dynamic identical to the seats,
        # so the summary must distill exactly the two opening positions
        self.assertEqual(sorted(str(cid) for cid in summary["distilledFrom"]), sorted(str(c) for c in turns))
        self.assertEqual(len(summary["positions"]), 2)

    def test_consensus_score_recorded_in_telemetry_note(self) -> None:
        seed, bundle_dir, keys_dir = _case(self.tmp, TRANSCRIPT + [CONSENSUS_RECORD])
        emitted_dir, _ = emit_case_bundle(seed, bundle_dir, keys_dir)
        problems, summary_result = verify_bundle(emitted_dir)
        self.assertEqual(problems, [], msg="\n".join(problems))
        from conclave_core.cbor import decode

        telemetries = [decode(p.read_bytes()) for p in sorted((emitted_dir / "artifacts").glob("*.cbor"))
                       if decode(p.read_bytes()).get("type") == "Telemetry"]
        consensus_notes = [
            t.get("note", "") for t in telemetries
            if "consensusScore=87" in (t.get("note") or "")
        ]
        self.assertEqual(len(consensus_notes), 1)
        self.assertIn("activeDissent=none", consensus_notes[0])
        self.assertEqual(summary_result["artifactCounts"].get("Round"), 1)  # early exit: no later round artifacts

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
