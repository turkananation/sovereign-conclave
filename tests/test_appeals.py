"""M5 appeal-engine tests: caps, windows, T2 gates, share math, ladder."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "scripts"), str(ROOT / "tests")):
    if path not in sys.path:
        sys.path.insert(0, path)

from conclave_core.appeals import (  # noqa: E402
    DEFAULT_WEIGHT_SHARE_MICRO,
    AppealCase,
    AppealError,
    mechanical_outcome_suggestion,
    weight_share_micro,
)
from conclave_core.artifacts import artifact_bytes, artifact_cid, make_evidence_ledger  # noqa: E402
from conclave_core.cbor import decode  # noqa: E402
from conclave_core.signing import (  # noqa: E402
    DOMAIN_APPEAL_PETITION,
    DOMAIN_APPEAL_SCREENING,
    DOMAIN_APPEAL_VERDICT,
    DOMAIN_ARBITER_RULING,
    make_signature_signed,
)
from conclave_core.verifier import verify_bundle  # noqa: E402
from scripts.artifact_emitter import (  # noqa: E402
    CaseSeed,
    append_artifacts_to_bundle,
    emit_case_bundle,
    supplement_ledger_artifact,
)
# transcript fixtures come from the emit suite: one canonical source of truth
from test_emit_bundle import CONSENSUS_RECORD, TRANSCRIPT  # noqa: E402

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

# Verdict issued at 09:00Z; the thirty-day default window closes 2026-11-20.
CASE_TIMESTAMP = "2026-10-21T09:00:00Z"
LATE_FILING = "2026-12-01T09:00:00Z"
TIMELY_FILING = "2026-10-22T09:00:00Z"
SCREENED_AT = "2026-10-23T09:00:00Z"
ADJUDICATED_AT = "2026-10-24T09:00:00Z"
RULED_AT = "2026-10-25T09:00:00Z"

# nobody convenes twice: the scaffold round convenes feynman, zhukov, marshall
APPELLATE_SEATS = ["conclave-washington", "conclave-toussaint", "conclave-hamilton"]
CUSTODIAL_NOTE = "signed by the conclave identity key on behalf of the named arbiter (v0.2 custodial signing)"


def _scaffold_bundle(root: Path, timestamp: str = CASE_TIMESTAMP) -> Path:
    """Emit the deterministic scaffold bundle the engine views operate on."""

    seed = CaseSeed(
        profile_id="architecture",
        problem="Should we split the analytics service?",
        timestamp=timestamp,
        seats=["conclave-feynman", "conclave-zhukov"],
        marshall_id="conclave-marshall",
        roster=ROSTER,
        ledger_entries=LEDGER_ENTRIES,
        transcript=None,
    )
    keys_dir = root / "keys"
    bundle_dir, _fingerprint = emit_case_bundle(seed, root / "case", keys_dir)
    return bundle_dir


def _vote(seat_id: str, weight: int) -> dict:
    return {"seatId": seat_id, "persona": None, "stance": "s", "weightMicro": weight}


def _dissent(seat_id: str) -> dict:
    return {"seatId": seat_id, "round": None, "grounds": "g", "citedLedgerIds": []}


def _tamper_verdict(bundle: Path) -> str:
    """Re-encode the verdict artifact under its original filename: a provable tamper."""

    for path in sorted((bundle / "artifacts").glob("*.cbor")):
        artifact = decode(path.read_bytes())
        if artifact.get("type") == "Verdict":
            artifact["recommendation"] += " Therefore: tampered by the e2e seed."
            path.write_bytes(artifact_bytes(artifact))
            return path.name
    raise AssertionError("no verdict artifact found to tamper")


class WeightShareMathTests(unittest.TestCase):
    """weight_share_micro: the T3 30% rule over verdict vote weights."""

    def test_two_of_three_equal_shares(self):
        verdict = {"votes": [_vote("a", 1_000_000), _vote("b", 1_000_000), _vote("c", 1_000_000)]}
        store = {f"d-{seat}": _dissent(seat) for seat in ("a", "b")}
        verdict["dissents"] = list(store)
        share = weight_share_micro(verdict, store.get)
        self.assertEqual(share, 666_666)  # floor(2/3 * 1e6)

    def test_proportional_weights(self):
        verdict = {"votes": [_vote("a", 700_000), _vote("b", 1_300_000)], "dissents": ["d-a"]}
        share = weight_share_micro(verdict, {"d-a": _dissent("a")}.get)
        self.assertEqual(share, 350_000)
        self.assertTrue(share >= DEFAULT_WEIGHT_SHARE_MICRO)

    def test_ignores_unresolvable_and_unenfranchised_dissents(self):
        verdict = {"votes": [_vote("a", 1_000_000)]}
        # missing link (None) and a dissent seat that holds no vote both vanish
        share = weight_share_micro(
            {**verdict, "dissents": ["d-ghost", "d-stranger"]},
            {"d-stranger": _dissent("stranger")}.get,
        )
        self.assertEqual(share, 0)

    def test_unknown_electorate(self):
        self.assertIsNone(weight_share_micro({"votes": []}, {}.get))
        self.assertIsNone(weight_share_micro({}, {}.get))


class ScaffoldStateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.engine = AppealCase(bundle_dir=_scaffold_bundle(Path(self._tmp.name)))

    def tearDown(self):
        self._tmp.cleanup()

    def test_case_state_from_bundle(self):
        self.assertIsNotNone(self.engine.verdict)
        self.assertEqual(self.engine.window_days, 30)
        self.assertEqual(self.engine.appeals, [])
        self.assertEqual((self.engine.trigger_count("T1"), self.engine.trigger_count("T2")), (0, 0))

    def test_trigger_support(self):
        ok, reason = self.engine.can_file("T2")
        self.assertTrue(ok)
        ok, reason = self.engine.can_file("T4")
        self.assertFalse(ok)
        self.assertIn("v0.3", reason)

    def test_no_votes_means_unknown_share(self):
        self.assertIsNone(self.engine.dissent_weight_share_micro())
        self.assertFalse(self.engine.t3_auto_scheduled())
        # the threshold parameter override still decides the gate mechanically
        self.assertTrue(self.engine.t3_auto_scheduled(share_micro=DEFAULT_WEIGHT_SHARE_MICRO))
        self.assertFalse(self.engine.t3_auto_scheduled(share_micro=DEFAULT_WEIGHT_SHARE_MICRO - 1))


class FilingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.engine = AppealCase(bundle_dir=_scaffold_bundle(Path(self._tmp.name)))

    def tearDown(self):
        self._tmp.cleanup()

    def _supplement(self):
        ledger_cid = self.engine.manifest["evidenceLedger"]
        original = self.engine.store[ledger_cid]
        entries = list(original["entries"]) + [
            {
                "id": f"E{len(original['entries']) + 1}",
                "item": "New: the production error budget burned twice in Q4.",
                "provenance": {"source": "appeal-T1 supplement", "kind": "user_assertion"},
                "handling": "Treat only as asserted input until screened.",
            }
        ]
        return make_evidence_ledger(entries, supersedes=ledger_cid)

    def test_t1_requires_supplement_ledger(self):
        with self.assertRaises(AppealError):
            self.engine.file_appeal(
                trigger="T1", grounds="new evidence", filed_by="conclave-feynman",
                filed_at=TIMELY_FILING,
            )

    def test_t1_filing_carries_window_and_supplement(self):
        appeal = self.engine.file_appeal(
            trigger="T1", grounds="two new incidents prove the risk", filed_by="conclave-feynman",
            filed_at=TIMELY_FILING, supplement_ledger=artifact_cid(self._supplement()),
        )
        self.assertEqual(appeal["trigger"], "T1")
        self.assertEqual(appeal["windowDays"], 30)
        self.assertIsNotNone(appeal["supplementLedger"])
        self.assertEqual(self.engine.trigger_count("T1"), 0)  # not persisted yet

    def test_t1_outside_window_rejected(self):
        engine = AppealCase(
            bundle_dir=_scaffold_bundle(Path(self._tmp.name), timestamp="2026-08-01T09:00:00Z")
        )
        with self.assertRaises(AppealError) as ctx:
            engine.file_appeal(
                trigger="T1", grounds="late", filed_by="conclave-feynman",
                filed_at=LATE_FILING, supplement_ledger=artifact_cid(self._supplement()),
            )
        self.assertIn("finality window", str(ctx.exception))

    def test_t2_is_window_exempt_but_needs_proven_checks(self):
        with self.assertRaises(AppealError):
            self.engine.file_appeal(
                trigger="T2", grounds="undocumented quorum suspicion", filed_by="conclave-feynman",
                filed_at=LATE_FILING,
            )
        appeal = self.engine.file_appeal(
            trigger="T2", grounds="procedural violation", filed_by="conclave-feynman",
            filed_at=LATE_FILING, proven_violation_checks=["signature-chain: verdict has no identity signature"],
        )
        self.assertEqual(appeal["trigger"], "T2")
        self.assertEqual(appeal["windowDays"], 30)

    def test_one_appeal_per_trigger_class(self):
        appeal = self.engine.file_appeal(
            trigger="T2", grounds="procedural violation", filed_by="conclave-feynman",
            filed_at=TIMELY_FILING, proven_violation_checks=["log: sth mismatch"],
        )
        self.engine.store[artifact_cid(appeal)] = appeal  # simulate persistence
        with self.assertRaises(AppealError) as ctx:
            self.engine.file_appeal(
                trigger="T2", grounds="second try", filed_by="conclave-feynman",
                filed_at=TIMELY_FILING, proven_violation_checks=["log: again"],
            )
        self.assertIn("anti-abuse cap", str(ctx.exception))


class LadderTests(unittest.TestCase):
    """Screening -> adjudication -> arbitration state machine."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.engine = AppealCase(bundle_dir=_scaffold_bundle(Path(self._tmp.name)))

    def tearDown(self):
        self._tmp.cleanup()

    def _file(self, engine, trigger, **kwargs):
        defaults = dict(
            trigger=trigger, grounds="grounds text", filed_by="conclave-feynman",
            filed_at=TIMELY_FILING,
        )
        defaults.update(kwargs)
        return engine.file_appeal(**defaults)

    def _persist(self, artifact):
        self.engine.store[artifact_cid(artifact)] = artifact
        return artifact_cid(artifact)

    def test_t2_proven_checks_grant_and_reversal_suggestion(self):
        problems = ["signature-chain: verdict  has no valid identity signature"]
        appeal = self._file(self.engine, "T2", proven_violation_checks=problems)
        appeal_cid = self._persist(appeal)
        granted, gate = self.engine.appeal_granted(appeal_cid)
        self.assertTrue(granted)
        self.assertIn("proven mechanically", gate)
        self.assertEqual(mechanical_outcome_suggestion(problems), "reverse")

    def test_outcome_suggestion_rules(self):
        self.assertEqual(mechanical_outcome_suggestion(["log: leaves hash mismatch"]), "reverse")
        self.assertEqual(mechanical_outcome_suggestion(["panel: quorum miss recorded"]), "remand")
        self.assertEqual(mechanical_outcome_suggestion([]), "remand")

    def test_tier_b_requires_a_granted_appeal(self):
        appeal = self._file(self.engine, "T1", supplement_ledger=artifact_cid(self._ledger()))
        appeal_cid = self._persist(appeal)
        with self.assertRaises(AppealError) as ctx:
            self.engine.adjudicate_appeal(
                appeal_cid=appeal_cid, tier="B", outcome="affirm", scope="scope",
                rationale="too early", recorded_at=TIMELY_FILING,
            )
        self.assertIn("awaits Marshall screening", str(ctx.exception))

    def test_t1_screening_rejected_then_admitted_latest_wins(self):
        engine = self.engine
        appeal_cid = self._persist(
            self._file(engine, "T1", supplement_ledger=artifact_cid(self._ledger()))
        )
        rejected = engine.screen_appeal(
            appeal_cid=appeal_cid, decision="rejected", screened_by="conclave-marshall",
            reasons="materiality unproven", screened_at="2026-10-23T09:00:00Z",
        )
        self._persist(rejected)
        granted, gate = engine.appeal_granted(appeal_cid)
        self.assertFalse(granted)
        self.assertIn("rejected", gate)
        admitted = engine.screen_appeal(
            appeal_cid=appeal_cid, decision="admitted", screened_by="conclave-marshall",
            reasons="supplement ledger proves materiality", screened_at="2026-10-24T09:00:00Z",
        )
        self._persist(admitted)
        granted, gate = engine.appeal_granted(appeal_cid)
        self.assertTrue(granted)
        self.assertIn("admitted", gate)

    def test_screening_only_applies_to_t1(self):
        appeal_cid = self._persist(self._file(self.engine, "T2", proven_violation_checks=["log: x"]))
        with self.assertRaises(ValueError):
            self.engine.screen_appeal(
                appeal_cid=appeal_cid, decision="admitted", screened_by="conclave-marshall",
                reasons="n/a", screened_at=TIMELY_FILING,
            )

    def test_tier_a_and_b_adjudicate_after_grant(self):
        appeal_cid = self._persist(
            self._file(self.engine, "T2", proven_violation_checks=["signature-chain: broken verdict sig"])
        )
        tier_a = self.engine.adjudicate_appeal(
            appeal_cid=appeal_cid, tier="A", outcome="remand", scope="grounds only",
            rationale="re-deliberate with the proven violation named in the record",
            recorded_at=TIMELY_FILING,
        )
        self.assertEqual((tier_a["tier"], tier_a["outcome"], tier_a["originalVerdict"] is not None),
                         ("A", "remand", True))
        tier_b = self.engine.adjudicate_appeal(
            appeal_cid=appeal_cid, tier="B", outcome="reverse", scope="grounds only",
            rationale="the verdict's identity signature does not resolve; reversal",
            panel_seats=["conclave-washington", "conclave-toussaint"],
            recorded_at=TIMELY_FILING,
        )
        self.assertEqual(tier_b["panelSeats"], ["conclave-washington", "conclave-toussaint"])

    def test_arbitration_references_and_values(self):
        with self.assertRaises(ValueError):
            self.engine.arbitrate_appeal(
                appeal_cid="bafyreiggg", arbiter="Judge Lang", disposition="dismiss",
                ruling="final", ruled_at=TIMELY_FILING,
            )
        appeal_cid = self._persist(self._file(self.engine, "T2", proven_violation_checks=["log: x"]))
        ruling = self.engine.arbitrate_appeal(
            appeal_cid=appeal_cid, arbiter="Judge Lang", disposition="dismiss",
            ruling=" abused discretion threshold; case closes", ruled_at=TIMELY_FILING,
        )
        self.assertEqual((ruling["arbiter"], ruling["disposition"]), ("Judge Lang", "dismiss"))

    def _ledger(self):
        ledger_cid = self.engine.manifest["evidenceLedger"]
        original = self.engine.store[ledger_cid]
        entries = list(original["entries"]) + [
            {
                "id": f"E{len(original['entries']) + 1}",
                "item": "New: the production error budget burned twice in Q4.",
                "provenance": {"source": "appeal-T1 supplement", "kind": "user_assertion"},
                "handling": "Treat only as asserted input until screened.",
            }
        ]
        return make_evidence_ledger(entries, supersedes=ledger_cid)


class PanelDrawTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.engine = AppealCase(bundle_dir=_scaffold_bundle(Path(self._tmp.name)))

    def tearDown(self):
        self._tmp.cleanup()

    def test_disjoint_drawing_excludes_convened_seats(self):
        # scaffold round participants: feynman, zhukov, marshall (convened)
        roster = [
            "conclave-feynman", "conclave-zhukov", "conclave-marshall",
            "conclave-washington", "conclave-toussaint",
        ]
        draw = self.engine.allowed_tier_b_panel(roster, size=2)
        self.assertEqual(draw, ["conclave-washington", "conclave-toussaint"])
        with self.assertRaises(ValueError):
            self.engine.allowed_tier_b_panel(roster, size=3)
        with self.assertRaises(ValueError):
            self.engine.allowed_tier_b_panel(roster, size=0)


class AppealBundleLifecycleTests(unittest.TestCase):
    """M5 acceptance flows against persisted bundles: emit -> engine -> log append -> verify.

    These mirror the live CLI reference runs (T2 reversal, T1 affirmation) and
    the auto-T3 gate at emit, so the roadmap round trip stays regression-proof.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _append_command(self, bundle: Path, principal: dict, domain: str, timestamp: str,
                        extra: list[dict] | None = None, note: str | None = None) -> None:
        """Mirror the runner CLI: identity-sign the principal document and append the step."""

        identity_seed = (self.root / "keys" / "identity.seed").read_bytes()
        signature = make_signature_signed(
            seed=identity_seed,
            domain=domain,
            payload=artifact_cid(principal),
            signed_at=timestamp,
            note=note,
        )
        append_artifacts_to_bundle(
            bundle,
            [*(extra or []), principal, signature],
            identity_seed=identity_seed,
            published_at=timestamp,
        )

    def test_scaffold_emit_files_no_appeal(self):
        engine = AppealCase(bundle_dir=_scaffold_bundle(self.root))
        self.assertEqual(engine.appeals, [])
        self.assertFalse(engine.t3_auto_scheduled())

    def test_auto_t3_fires_at_emit_on_heavy_dissent(self):
        dissenting = dict(CONSENSUS_RECORD)
        dissenting["response"] = '{"consensusScore": 61, "activeDissent": ["conclave-zhukov"]}'
        seed = CaseSeed(
            profile_id="architecture",
            problem="Should we split the analytics service?",
            timestamp=CASE_TIMESTAMP,
            seats=["conclave-feynman", "conclave-zhukov"],
            marshall_id="conclave-marshall",
            roster=ROSTER,
            ledger_entries=LEDGER_ENTRIES,
            transcript=[*TRANSCRIPT, dissenting],
        )
        bundle, _fingerprint = emit_case_bundle(seed, self.root / "case", self.root / "keys")

        engine = AppealCase(bundle_dir=bundle)
        self.assertEqual(engine.dissent_weight_share_micro(), 500_000)
        self.assertTrue(engine.t3_auto_scheduled())
        auto_cid, auto = engine.appeals[0]
        self.assertEqual(auto["trigger"], "T3")
        self.assertEqual(auto["filedBy"], "mechanical:T3")
        self.assertIn("automatic", auto["grounds"])
        granted, gate = engine.appeal_granted(auto_cid)
        self.assertTrue(granted, msg=gate)
        self.assertIn("T3", gate)

        problems, summary = verify_bundle(bundle)
        self.assertEqual(problems, [], msg=str(problems))
        self.assertEqual(summary["status"], "VERIFIED")
        log = json.loads((bundle / "bundle.json").read_text(encoding="utf-8"))["log"]
        self.assertEqual(len(log["leaves"]), 2)  # verdict + the automatic appeal
        self.assertEqual(len(log["consistency"]), 1)

    def test_t2_tamper_is_proven_then_reversed_on_appeal(self):
        bundle = _scaffold_bundle(self.root)
        verdict_name = _tamper_verdict(bundle)

        engine = AppealCase(bundle_dir=bundle)
        problems = engine.validate_bundle()
        hash_problems = [problem for problem in problems if "content hashes to" in problem]
        self.assertEqual(len(hash_problems), 1, msg=str(problems))
        self.assertIn(verdict_name, hash_problems[0])
        self.assertIn("content hashes to", problems[0])
        # artifact-content tamper is remand-class mechanically; reversal stays human (D-4)
        self.assertEqual(mechanical_outcome_suggestion(problems), "remand")

        appeal = engine.file_appeal(
            trigger="T2",
            grounds="proven procedural violations attached as provenViolationChecks",
            filed_by="conclave-feynman",
            filed_at=TIMELY_FILING,
            proven_violation_checks=problems,
        )
        self._append_command(bundle, appeal, DOMAIN_APPEAL_PETITION, TIMELY_FILING)

        granted_engine = AppealCase(bundle_dir=bundle)
        appeal_cid = next(cid for cid, _ in granted_engine.appeals)
        granted, gate = granted_engine.appeal_granted(appeal_cid)
        self.assertTrue(granted, msg=gate)
        self.assertIn("proven mechanically", gate)

        panel = granted_engine.allowed_tier_b_panel(
            [seat["id"] for seat in ROSTER["seats"]] + APPELLATE_SEATS, size=3
        )
        self.assertEqual(panel, APPELLATE_SEATS)  # disjoint from every convened seat

        tier_b = granted_engine.adjudicate_appeal(
            appeal_cid=appeal_cid,
            tier="B",
            outcome="reverse",
            scope="appeal grounds and cited evidence only",
            rationale="the recorded recommendation is not what the conclave advised",
            panel_seats=panel,
            recorded_at=ADJUDICATED_AT,
        )
        self.assertEqual(tier_b["panelSeats"], panel)
        self._append_command(bundle, tier_b, DOMAIN_APPEAL_VERDICT, ADJUDICATED_AT)

        ruling = AppealCase(bundle_dir=bundle).arbitrate_appeal(
            appeal_cid=appeal_cid,
            arbiter="Marisol Vale",
            disposition="reverse",
            ruling="the tampered record reverses; a re-deliberation must be convened",
            ruled_at=RULED_AT,
        )
        self._append_command(bundle, ruling, DOMAIN_ARBITER_RULING, RULED_AT, note=CUSTODIAL_NOTE)

        # the tamper stays provable, and the extended log stays valid
        problems_after, summary = verify_bundle(bundle)
        self.assertEqual(problems_after, problems)
        counts = summary["artifactCounts"]
        self.assertEqual(counts["Appeal"], 1)
        self.assertEqual(counts["AppealVerdict"], 1)
        self.assertEqual(counts["ArbiterRuling"], 1)
        log = json.loads((bundle / "bundle.json").read_text(encoding="utf-8"))["log"]
        self.assertEqual(len(log["leaves"]), 4)  # verdict, appeal, appellate verdict, ruling
        self.assertEqual(len(log["sthCids"]), 5)

    def test_t1_supplement_screening_then_affirm(self):
        bundle = _scaffold_bundle(self.root)
        engine = AppealCase(bundle_dir=bundle)
        supplement = supplement_ledger_artifact(
            engine,
            [{
                "item": "Note: the repository passed a second independent war-game review.",
                "source_type": "user_assertion",
                "source": "appeal-T1 fixture",
                "provenance": "Imported fixture note for the supplement ledger",
                "handling": "Treat only as asserted input.",
            }],
            created_at=TIMELY_FILING,
        )
        appeal = engine.file_appeal(
            trigger="T1",
            grounds="the supplement carries material evidence absent from the frozen ledger",
            filed_by="conclave-zhukov",
            filed_at=TIMELY_FILING,
            supplement_ledger=artifact_cid(supplement),
        )
        self._append_command(bundle, appeal, DOMAIN_APPEAL_PETITION, TIMELY_FILING, extra=[supplement])

        reloaded = AppealCase(bundle_dir=bundle)
        appeal_cid = next(cid for cid, _ in reloaded.appeals)
        granted, gate = reloaded.appeal_granted(appeal_cid)
        self.assertFalse(granted)
        self.assertIn("awaits", gate)

        screening = reloaded.screen_appeal(
            appeal_cid=appeal_cid,
            decision="admitted",
            screened_by="conclave-marshall",
            reasons="the supplement is material and absent from the frozen ledger",
            screened_at=SCREENED_AT,
        )
        self._append_command(bundle, screening, DOMAIN_APPEAL_SCREENING, SCREENED_AT)

        adjudicating = AppealCase(bundle_dir=bundle)
        granted, gate = adjudicating.appeal_granted(appeal_cid)
        self.assertTrue(granted, msg=gate)
        tier_a = adjudicating.adjudicate_appeal(
            appeal_cid=appeal_cid,
            tier="A",
            outcome="affirm",
            scope="appeal grounds and cited evidence only",
            rationale="the supplement widens context; the recorded advice stands",
            recorded_at=ADJUDICATED_AT,
        )
        self._append_command(bundle, tier_a, DOMAIN_APPEAL_VERDICT, ADJUDICATED_AT)

        closing = AppealCase(bundle_dir=bundle)
        ruling = closing.arbitrate_appeal(
            appeal_cid=appeal_cid,
            arbiter="Marisol Vale",
            disposition="affirm",
            ruling="closed on the affirmed advice",
            ruled_at=RULED_AT,
        )
        self._append_command(bundle, ruling, DOMAIN_ARBITER_RULING, RULED_AT, note=CUSTODIAL_NOTE)

        problems, summary = verify_bundle(bundle)
        self.assertEqual(problems, [], msg=str(problems))
        self.assertEqual(summary["status"], "VERIFIED")
        counts = summary["artifactCounts"]
        self.assertEqual(counts["EvidenceLedger"], 2)  # frozen ledger + supplement
        for kind in ("Appeal", "AppealScreening", "AppealVerdict", "ArbiterRuling"):
            self.assertEqual(counts[kind], 1, msg=kind)
        log = json.loads((bundle / "bundle.json").read_text(encoding="utf-8"))["log"]
        self.assertEqual(len(log["leaves"]), 6)
        self.assertEqual(len(log["sthCids"]), 7)


if __name__ == "__main__":
    unittest.main()
