"""M6 store tests: append-only artifacts, rebuildable projections, Merkle log."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "scripts"), str(ROOT / "tests")):
    if path not in sys.path:
        sys.path.insert(0, path)

from conclave_core.artifacts import artifact_cid, make_appeal, raw_cid  # noqa: E402
from conclave_core.cbor import decode  # noqa: E402
from conclave_core.merkle import tree_hash, verify_consistency, verify_inclusion  # noqa: E402
from conclave_server.store import ArtifactStore  # noqa: E402
from test_emit_bundle import LEDGER_ENTRIES, ROSTER  # canonical emit fixtures
from scripts.artifact_emitter import CaseSeed, emit_case_bundle  # noqa: E402

TIME = "2026-10-21T09:00:00Z"
LATER = "2026-10-23T09:00:00Z"


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = ArtifactStore(self.root / "store.sqlite3")

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def _scaffold_bundle(self) -> Path:
        seed = CaseSeed(
            profile_id="architecture",
            problem="Should we split the analytics service?",
            timestamp=TIME,
            seats=["conclave-feynman", "conclave-zhukov"],
            marshall_id="conclave-marshall",
            roster=ROSTER,
            ledger_entries=LEDGER_ENTRIES,
            transcript=None,
        )
        bundle, _fingerprint = emit_case_bundle(seed, self.root / "case", self.root / "keys")
        return bundle

    def _ingest_bundle(self, bundle: Path) -> None:
        for path in sorted((bundle / "artifacts").glob("*.cbor")):
            self.store.ingest(decode(path.read_bytes()), TIME)

    def _appeal(self, manifest: dict):
        return make_appeal(
            verdict=manifest["verdict"],
            case_manifest=artifact_cid(manifest),
            trigger="T2",
            grounds="store fixture: proven procedural violation",
            filed_by="conclave-feynman",
            filed_at=LATER,
            proven_violation_checks=["log: fixture"],
            window_days=30,
        )

    def test_ingest_round_trip_dedup_and_immutability(self):
        bundle = self._scaffold_bundle()
        self._ingest_bundle(bundle)

        artifacts = [decode(path.read_bytes()) for path in sorted((bundle / "artifacts").glob("*.cbor"))]
        question = next(a for a in artifacts if a.get("type") == "Question")
        question_cid = artifact_cid(question)

        self.assertEqual(self.store.get(question_cid), question)
        self.assertEqual(self.store.raw(question_cid), self.store.raw(question_cid))
        self.assertNotEqual(self.store.raw(question_cid), b"")

        # content-addressed dedupe: re-ingest leaves the first created_at standing
        later = self.store.ingest(question, LATER)
        self.assertEqual(later, question_cid)
        self.assertEqual(self.store.created_at(question_cid), TIME)
        self.assertEqual(len(self.store.all_cids()), len({str(c) for c in self.store.all_cids()}))

    def test_projections_track_ingest_and_rebuild_repairs_drift(self):
        bundle = self._scaffold_bundle()
        self._ingest_bundle(bundle)

        artifacts = [decode(path.read_bytes()) for path in sorted((bundle / "artifacts").glob("*.cbor"))]
        final_manifest = next(
            m for m in artifacts if m.get("type") == "DeliberationManifest" and m.get("verdict")
        )
        self.store.ingest(self._appeal(final_manifest), LATER)

        counts = self.store.rebuild_projections()
        paired = {
            "proj_manifests": "DeliberationManifest",
            "proj_rounds": "Round",
            "proj_turns": "Turn",
            "proj_verdicts": "Verdict",
            "proj_appeals": "Appeal",
        }
        for table, type_name in paired.items():
            self.assertEqual(counts[table], len(self.store.by_type(type_name)), msg=table)
        self.assertEqual(counts["proj_appeals"], 1)

        # projections are discardable: drift repairs from artifacts alone
        drift = sqlite3.connect(str(self.root / "store.sqlite3"))
        try:
            drift.execute("DELETE FROM proj_appeals")
            drift.commit()
        finally:
            drift.close()
        repaired = self.store.rebuild_projections()
        self.assertEqual(repaired["proj_appeals"], 1)

    def test_log_leaves_heads_and_proofs(self):
        bundle = self._scaffold_bundle()
        self._ingest_bundle(bundle)
        order = self.store.by_type("Question") + self.store.by_type("EvidenceLedger") + [
            self.store.by_type("Verdict")[0]
        ]
        self.assertEqual(len(order), 3)

        timed = ["2026-10-22T09:00:00Z", "2026-10-23T09:00:00Z", "2026-10-24T09:00:00Z"]
        case_ref = "case-2026102109"
        for index, (cid, stamp) in enumerate(zip(order, timed), start=1):
            size, _root = self.store.append_log_leaf(cid, stamp, case_ref=case_ref)
            self.assertEqual(size, index)

        leaves = self.store.leaves(case_ref)
        self.assertEqual(leaves, order)
        heads = self.store.heads(case_ref)
        self.assertEqual([head[0] for head in heads], [1, 2, 3])
        for head in heads:
            expected = [leaf.cid_bytes() for leaf in leaves[: head[0]]]
            self.assertEqual(head[1], tree_hash(expected))

        # logs are case-scoped: an unrelated case has an independent empty log
        self.assertEqual(self.store.leaf_count("some-other-case"), 0)
        self.assertEqual(self.store.heads("some-other-case"), [])

        # one size-3 tree: consistency proofs verify pairwise; inclusion verifies
        root = heads[-1][1]
        for m in (1, 2):
            proof = self.store.consistency_proof(case_ref, m, 3)
            old_root = [head for head in heads if head[0] == m][0][1]
            self.assertTrue(verify_consistency(m, 3, proof, old_root, root))
        proof = self.store.inclusion_proof(case_ref, 1, 3)
        self.assertTrue(verify_inclusion(leaves[1].cid_bytes(), 1, proof, 3, root))
        self.assertEqual(self.store.leaf_count(case_ref), 3)
        self.assertEqual(self.store.latest_head(case_ref)[0], 3)

        duplicate, foreign = leaves[1], raw_cid(b"foreign artifact never ingested")
        with self.assertRaises(ValueError):
            self.store.append_log_leaf(duplicate, LATER, case_ref=case_ref)
        with self.assertRaises(ValueError):
            self.store.append_log_leaf(foreign, LATER, case_ref=case_ref)
        with self.assertRaises(ValueError):
            self.store.consistency_proof(case_ref, 0, 3)
        with self.assertRaises(ValueError):
            self.store.inclusion_proof(case_ref, 3, 3)


if __name__ == "__main__":
    unittest.main()
