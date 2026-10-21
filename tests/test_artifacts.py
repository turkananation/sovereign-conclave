"""Tests for the conclave artifact model and DAG verification."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conclave_core.artifacts import (
    ArtifactError,
    CODEC_VERSION,
    artifact_bytes,
    artifact_cid,
    make_dissent,
    make_evidence_ledger,
    make_manifest,
    make_panel,
    make_persona,
    make_protocol_params,
    make_question,
    make_round,
    make_summary,
    make_turn,
    make_verdict,
    raw_cid,
    validate_artifact,
    verify_manifest,
)
from conclave_core.cbor import decode, encode
from conclave_core.cid import Cid

LEDGER_ENTRIES = [
    {
        "id": "E1",
        "item": "The validation stack was green on 2026-06-01.",
        "provenance": {"source": "CI run log", "kind": "command output"},
        "handling": "primary source",
    },
    {
        "id": "E2",
        "item": "The roster carries 33 seats and 24 profiles.",
        "provenance": {"source": "configs/conclave-roster.json", "kind": "local file"},
        "handling": "local file",
    },
    {
        "id": "E3",
        "item": "Release holds until the rollback owner signs off.",
        "provenance": {"source": "product note 2026-10-01", "kind": "user note"},
        "handling": "contested",
    },
]


def build_persona(seat_id: str, display: str, tier: str, model: str, partner: str | None = None) -> dict:
    return make_persona(
        seat_id=seat_id,
        display_name=display,
        tier=tier,
        lens=f"{display} lens",
        stance=f"{display} argues from {tier.lower()} concerns.",
        how_you_argue=[
            "Names the decisive evidence first.",
            "Attacks the strongest opposing claim, not the weakest.",
            "Concedes when the ledger contradicts the stance.",
        ],
        characteristic_bias=f"Overweights {tier.lower()} framing.",
        is_not=["Not any other seat.", "Not a capability claim."],
        model=model,
        version="roster-0.1.0",
        polarity_partner=partner,
    )


class SampleDag:
    """Builds a small, fully valid deliberation DAG for tests."""

    def __init__(self) -> None:
        self.question = make_question(
            "Should we split the analytics service?",
            options=[
                {"id": "split", "label": "Split into its own service"},
                {"id": "keep", "label": "Keep in the monolith"},
            ],
            asked_by="platform team",
            asked_at="2026-10-01T09:00:00Z",
        )
        self.ledger = make_evidence_ledger(LEDGER_ENTRIES, created_at="2026-10-01T09:05:00Z")
        self.personas = {
            seat: build_persona(seat, display, tier, model, partner)
            for seat, display, tier, model, partner in (
                ("conclave-feynman", "Richard Feynman", "Inner Sanctum", "sonnet", None),
                ("conclave-zhukov", "Georgy Zhukov", "General", "sonnet", "conclave-washington"),
                ("conclave-washington", "George Washington", "General", "sonnet", "conclave-zhukov"),
                ("conclave-marshall", "Marshall", "Justice (always)", "opus", None),
            )
        }
        seats = [
            {
                "seatId": seat,
                "persona": artifact_cid(persona),
                "model": persona["model"],
            }
            for seat, persona in self.personas.items()
        ]
        self.panel = make_panel(seats, convened_at="2026-10-01T09:10:00Z", quorum=4)
        self.params = make_protocol_params(
            recorded_by="session-orchestrator", quorum=4, max_rounds=4,
        )

        manifest_v1 = make_manifest(
            case_id="case-2026-10-01-analytics",
            question=artifact_cid(self.question),
            evidence_ledger=artifact_cid(self.ledger),
            panel=artifact_cid(self.panel),
            protocol_params=artifact_cid(self.params),
            title="Analytics service split",
            opened_at="2026-10-01T09:00:30Z",
        )
        self.manifests: list[dict] = [manifest_v1]

        self.rounds: list[dict] = []
        self.turns: list[list[dict]] = []
        self.summaries: list[dict] = []
        stances = {
            0: [
                ("conclave-feynman", "split", ["E2"]),
                ("conclave-zhukov", "keep", ["E1", "E2"]),
                ("conclave-washington", "split", ["E1"]),
            ],
            1: [
                ("conclave-feynman", "split", ["E2"]),
                ("conclave-zhukov", "keep", ["E3"]),
                ("conclave-washington", "keep", ["E1", "E3"]),
            ],
        }
        previous_round_cid = None
        for index in range(2):
            turns_out = []
            for seat_id in ("conclave-feynman", "conclave-zhukov", "conclave-washington"):
                turns_out.append(
                    make_turn(
                        round_index=index,
                        seat_id=seat_id,
                        persona=artifact_cid(self.personas[seat_id]),
                        input_context_hash=raw_cid(f"prompt-{index}-{seat_id}".encode()),
                        model_id="claude-sonnet-4",
                        temperature_micro=1_000_000,
                        top_p_micro=1_000_000,
                        max_output_tokens=4096,
                        seed=7,
                        output=raw_cid(f"output-{index}-{seat_id}".encode()),
                        citations=["E1", "E2"] if seat_id != "conclave-feynman" else ["E2"],
                        tokens={"inputTokens": 900, "outputTokens": 340, "cacheReadTokens": 0},
                        cost_micro_usd=4200,
                        recorded_at=f"2026-10-01T09:2{index}:00Z",
                        provider_run=False,
                    )
                )
            self.turns.append(turns_out)
            turn_cids = [artifact_cid(t) for t in turns_out]
            summary = make_summary(
                round_index=index,
                distilled_from=turn_cids,
                positions=[
                    {"seatId": seat, "stance": stance, "citations": cites}
                    for seat, stance, cites in stances[index]
                ],
                summary_text=(
                    "Round carries gathered stances from the ledger; Zhukov resists on E1/E3."
                    if index == 1
                    else "Two seats favor the split on E1/E2; Zhukov resists on readiness."
                ),
                open_disagreements=["Zhukov vs the majority on rolling deployment risk."],
                written_at=f"2026-10-01T09:3{index}:00Z",
                model_id="haiku-class",
                word_count=48,
            )
            self.summaries.append(summary)
            self.rounds.append(
                make_round(
                    index=index,
                    prev=previous_round_cid,
                    status="committed",
                    participants=[
                        "conclave-feynman", "conclave-zhukov",
                        "conclave-washington", "conclave-marshall",
                    ],
                    turns=turn_cids,
                    distilled_summary=artifact_cid(summary),
                    opened_at=f"2026-10-01T09:1{index}:00Z",
                    closed_at=f"2026-10-01T09:35:0{index}Z",
                )
            )
            previous_round_cid = artifact_cid(self.rounds[-1])
            self.manifests.append(
                make_manifest(
                    case_id="case-2026-10-01-analytics",
                    question=artifact_cid(self.question),
                    evidence_ledger=artifact_cid(self.ledger),
                    panel=artifact_cid(self.panel),
                    protocol_params=artifact_cid(self.params),
                    rounds=[artifact_cid(r) for r in self.rounds],
                    supersedes=artifact_cid(self.manifests[-1]),
                    title="Analytics service split",
                    opened_at="2026-10-01T09:00:30Z",
                )
            )

        self.dissent = make_dissent(
            round_cid=artifact_cid(self.rounds[-1]),
            seat_id="conclave-zhukov",
            persona=artifact_cid(self.personas["conclave-zhukov"]),
            grounds="E1 overweights CI stability; rolling-cutoff deployment risk is unweighed.",
            cited_ledger_ids=["E1"],
            filed_at="2026-10-01T09:40:00Z",
        )
        pre_verdict_manifest = self.manifests[-1]
        self.verdict = make_verdict(
            manifest=artifact_cid(pre_verdict_manifest),
            final_round=artifact_cid(self.rounds[-1]),
            decision="Split the analytics service behind a feature-flagged extraction.",
            recommendation=(
                "The Sovereign Conclave advises you to run a 30-day flagged extraction "
                "of the analytics service before committing."
            ),
            votes=[
                {
                    "seatId": "conclave-feynman",
                    "persona": artifact_cid(self.personas["conclave-feynman"]),
                    "stance": "split",
                    "weightMicro": 1_000_000,
                },
                {
                    "seatId": "conclave-zhukov",
                    "persona": artifact_cid(self.personas["conclave-zhukov"]),
                    "stance": "keep",
                    "weightMicro": 1_000_000,
                },
                {
                    "seatId": "conclave-washington",
                    "persona": artifact_cid(self.personas["conclave-washington"]),
                    "stance": "split",
                    "weightMicro": 1_000_000,
                },
            ],
            confidence="medium",
            dissents=[artifact_cid(self.dissent)],
            what_would_change_it="If stability evidence shows 3+ failed extractions, revisit.",
            dissent_recorded_note="Zhukov's dissent is preserved verbatim.",
            issued_at="2026-10-01T10:00:00Z",
        )
        self.root = make_manifest(
            case_id="case-2026-10-01-analytics",
            question=artifact_cid(self.question),
            evidence_ledger=artifact_cid(self.ledger),
            panel=artifact_cid(self.panel),
            protocol_params=artifact_cid(self.params),
            rounds=[artifact_cid(r) for r in self.rounds],
            verdict=artifact_cid(self.verdict),
            supersedes=artifact_cid(pre_verdict_manifest),
            title="Analytics service split",
            opened_at="2026-10-01T09:00:30Z",
        )
        self.manifests.append(self.root)

    def put_everything(self, store: "Store") -> None:
        for artifact in (self.question, self.ledger, self.panel, self.params):
            store.put(artifact)
        for persona in self.personas.values():
            store.put(persona)
        for round_artifact in self.rounds:
            store.put(round_artifact)
        for summary in self.summaries:
            store.put(summary)
        for turns in self.turns:
            for turn in turns:
                store.put(turn)
        for manifest in self.manifests:
            store.put(manifest)
        store.put(self.dissent)
        store.put(self.verdict)


class Store:
    """In-memory artifact store keyed by CID; resolver back end for tests."""

    def __init__(self) -> None:
        self._by_cid: dict[bytes, dict] = {}

    def put(self, artifact: dict) -> None:
        self._by_cid[artifact_cid(artifact).cid_bytes()] = artifact

    def replace(self, cid: Cid, artifact) -> None:
        self._by_cid[cid.cid_bytes()] = artifact

    def get(self, cid: Cid):
        found = self._by_cid.get(cid.cid_bytes())
        return copy.deepcopy(found) if found is not None else None

    def as_resolver(self):
        return self.get


class TestArtifactStructure(unittest.TestCase):
    def test_every_artifact_type_validates(self) -> None:
        dag = SampleDag()
        artifacts = [
            dag.question, dag.ledger, dag.panel, dag.params,
            dag.dissent, dag.verdict, dag.root,
            *dag.personas.values(), *dag.rounds, *dag.manifests,
            *(turn for turns in dag.turns for turn in turns), *dag.summaries,
        ]
        self.assertEqual(len(artifacts), 25)
        for artifact in artifacts:
            with self.subTest(artifact_type=artifact["type"]):
                validate_artifact(artifact)

    def test_codec_version_present_on_all_types(self) -> None:
        dag = SampleDag()
        checked = (
            dag.question, dag.ledger, dag.panel, dag.params, dag.root,
            dag.verdict, dag.dissent, dag.rounds[1], dag.turns[0][0],
            dag.summaries[0], dag.personas["conclave-zhukov"],
        )
        for artifact in checked:
            self.assertEqual(artifact.get("codecVersion"), CODEC_VERSION)

    def test_codec_version_tamper_rejected(self) -> None:
        dag = SampleDag()
        missing = copy.deepcopy(dag.question)
        del missing["codecVersion"]
        with self.assertRaises(ArtifactError):
            validate_artifact(missing)
        bumped = copy.deepcopy(dag.question)
        bumped["codecVersion"] = 2
        with self.assertRaises(ArtifactError):
            validate_artifact(bumped)
        boolean = copy.deepcopy(dag.question)
        boolean["codecVersion"] = True  # bool must not pass as int 1
        with self.assertRaises(ArtifactError):
            validate_artifact(boolean)

    def test_unknown_artifact_type_rejected(self) -> None:
        with self.assertRaises(ArtifactError):
            validate_artifact({"type": "RoundTable", "codecVersion": CODEC_VERSION})

    def test_floats_rejected_in_artifacts(self) -> None:
        dag = SampleDag()
        params = copy.deepcopy(dag.params)
        params["costMultiplier"] = 1.5
        with self.assertRaises(ArtifactError):
            validate_artifact(params)
        turn = copy.deepcopy(dag.turns[0][0])
        turn["costMicroUsd"] = 4.2
        with self.assertRaises(ArtifactError):
            validate_artifact(turn)
        turn = copy.deepcopy(dag.turns[0][0])
        turn["tokens"] = {"inputTokens": 2.0}
        with self.assertRaises(ArtifactError):
            validate_artifact(turn)

    def test_verdict_requires_advice_language(self) -> None:
        dag = SampleDag()
        bad = copy.deepcopy(dag.verdict)
        bad["recommendation"] = "Deploy now."
        with self.assertRaises(ArtifactError):
            validate_artifact(bad)

    def test_verdict_bearing_manifest_requires_supersedes(self) -> None:
        dag = SampleDag()
        plain = make_manifest(
            case_id="case-x",
            question=artifact_cid(dag.question),
            evidence_ledger=artifact_cid(dag.ledger),
            panel=artifact_cid(dag.panel),
            protocol_params=artifact_cid(dag.params),
        )
        self.assertIsNone(plain["verdict"])
        with_verdict = copy.deepcopy(plain)
        with_verdict["verdict"] = artifact_cid(dag.params)
        with self.assertRaises(ArtifactError):
            validate_artifact(with_verdict)
        corrected = copy.deepcopy(with_verdict)
        corrected["supersedes"] = artifact_cid(dag.manifests[0])
        validate_artifact(corrected)  # structurally valid

    def test_ledger_ids_contiguous(self) -> None:
        entries = [
            copy.deepcopy(LEDGER_ENTRIES[0]),
            dict(copy.deepcopy(LEDGER_ENTRIES[2]), id="E3"),
        ]
        with self.assertRaises(ArtifactError):
            make_evidence_ledger(entries)

    def test_marshall_must_be_convened(self) -> None:
        dag = SampleDag()
        persona = dag.personas["conclave-feynman"]
        with self.assertRaises(ArtifactError):
            make_panel([
                {
                    "seatId": "conclave-feynman",
                    "persona": artifact_cid(persona),
                    "model": "sonnet",
                }
            ])


class TestCanonicalization(unittest.TestCase):
    def test_manifest_round_trips_with_stable_cid(self) -> None:
        dag = SampleDag()
        canonical = artifact_bytes(dag.root)
        decoded = decode(canonical)
        self.assertEqual(encode(decoded), canonical)
        self.assertEqual(decoded, dag.root)
        self.assertEqual(artifact_cid(decoded), artifact_cid(dag.root))

    def test_tampering_changes_cid(self) -> None:
        dag = SampleDag()
        original = artifact_cid(dag.verdict)
        tampered = copy.deepcopy(dag.verdict)
        tampered["confidence"] = "high"
        self.assertNotEqual(artifact_cid(tampered), original)

    def test_input_context_and_output_are_raw_links(self) -> None:
        dag = SampleDag()
        turn = dag.turns[0][0]
        self.assertEqual(turn["inputContextHash"].cid_bytes()[1], 0x55)  # raw codec
        self.assertEqual(turn["output"].cid_bytes()[1], 0x55)


class TestDagVerification(unittest.TestCase):
    def setUp(self) -> None:
        self.dag = SampleDag()
        self.store = Store()
        self.dag.put_everything(self.store)

    def test_golden_dag_verifies_clean(self) -> None:
        self.assertEqual(verify_manifest(self.dag.root, self.store.as_resolver()), [])

    def test_tampered_artifact_detected(self) -> None:
        summary_cid = artifact_cid(self.dag.summaries[0])
        tampered = copy.deepcopy(self.dag.summaries[0])
        tampered["summaryText"] = "Tampered summary text."
        self.store.replace(summary_cid, tampered)
        problems = verify_manifest(self.dag.root, self.store.as_resolver())
        self.assertTrue(any("CID mismatch" in p for p in problems), problems)

    def test_missing_artifact_detected(self) -> None:
        turn_cid = artifact_cid(self.dag.turns[1][1])
        self.store.replace(turn_cid, None)
        problems = verify_manifest(self.dag.root, self.store.as_resolver())
        self.assertTrue(any("not found" in p for p in problems), problems)

    def test_wrong_turn_round_index_detected(self) -> None:
        # Standalone: a turn stamped for round 1 but attached inside round 0.
        wrong_turn = make_turn(
            round_index=1,
            seat_id="conclave-zhukov",
            persona=artifact_cid(self.dag.personas["conclave-zhukov"]),
            input_context_hash=raw_cid(b"prompt-wrong-index"),
            model_id="claude-sonnet-4",
            seed=None,
            output=raw_cid(b"output-wrong-index"),
            citations=["E1"],
            recorded_at="2026-10-01T09:50:00Z",
        )
        self.store.put(wrong_turn)
        placeholder = make_summary(
            round_index=0,
            distilled_from=[artifact_cid(wrong_turn)],
            positions=[{"seatId": "conclave-zhukov", "stance": "keep", "citations": ["E1"]}],
            summary_text="Wrongly rounded turn distilled into a summary.",
            open_disagreements=[],
            written_at="2026-10-01T09:50:30Z",
            model_id="haiku-class",
        )
        self.store.put(placeholder)
        round0 = make_round(
            index=0,
            prev=None,
            status="committed",
            participants=["conclave-zhukov", "conclave-marshall"],
            turns=[artifact_cid(wrong_turn)],
            distilled_summary=artifact_cid(placeholder),
            opened_at="2026-10-01T09:40:00Z",
        )
        self.store.put(round0)
        manifest = make_manifest(
            case_id="case-retry",
            question=artifact_cid(self.dag.question),
            evidence_ledger=artifact_cid(self.dag.ledger),
            panel=artifact_cid(self.dag.panel),
            protocol_params=artifact_cid(self.dag.params),
            rounds=[artifact_cid(round0)],
        )
        problems = verify_manifest(manifest, self.store.as_resolver())
        self.assertTrue(any("roundIndex" in p for p in problems), problems)

    def test_broken_round_chain_detected(self) -> None:
        # Standalone: round 1 prev-links a round CID that is not its parent.
        decoy = make_round(
            index=1,
            prev=None,
            status="committed",
            participants=["conclave-feynman", "conclave-marshall"],
            opened_at="2026-10-01T09:48:00Z",
        )
        self.store.put(decoy)
        shim = make_round(
            index=0,
            prev=None,
            status="committed",
            participants=["conclave-zhukov", "conclave-marshall"],
            opened_at="2026-10-01T09:40:00Z",
        )
        broken = make_round(
            index=1,
            prev=artifact_cid(decoy),  # not the shim anyone will list before it
            status="committed",
            participants=["conclave-feynman", "conclave-marshall"],
            opened_at="2026-10-01T09:49:00Z",
        )
        self.store.put(shim)
        self.store.put(broken)
        manifest = make_manifest(
            case_id="case-retry",
            question=artifact_cid(self.dag.question),
            evidence_ledger=artifact_cid(self.dag.ledger),
            panel=artifact_cid(self.dag.panel),
            protocol_params=artifact_cid(self.dag.params),
            rounds=[artifact_cid(shim), artifact_cid(broken)],
        )
        problems = verify_manifest(manifest, self.store.as_resolver())
        self.assertTrue(any("does not match the previous round link" in p for p in problems), problems)

    def test_verdict_final_round_mismatch_detected(self) -> None:
        rounds = [artifact_cid(r) for r in self.dag.rounds]
        base = make_manifest(
            case_id="case-retry",
            question=artifact_cid(self.dag.question),
            evidence_ledger=artifact_cid(self.dag.ledger),
            panel=artifact_cid(self.dag.panel),
            protocol_params=artifact_cid(self.dag.params),
            rounds=rounds[:1],
        )
        self.store.put(base)
        pre_verdict = make_manifest(
            case_id="case-retry",
            question=artifact_cid(self.dag.question),
            evidence_ledger=artifact_cid(self.dag.ledger),
            panel=artifact_cid(self.dag.panel),
            protocol_params=artifact_cid(self.dag.params),
            rounds=rounds,
            supersedes=artifact_cid(base),
        )
        self.store.put(pre_verdict)
        bad_verdict = make_verdict(
            manifest=artifact_cid(pre_verdict),
            final_round=rounds[0],  # wrong: the last round is rounds[-1]
            decision="d",
            recommendation="The Sovereign Conclave advises you to consider.",
            votes=[],
            confidence="low",
            issued_at="2026-10-01T10:05:00Z",
        )
        self.store.put(bad_verdict)
        root = make_manifest(
            case_id="case-retry",
            question=artifact_cid(self.dag.question),
            evidence_ledger=artifact_cid(self.dag.ledger),
            panel=artifact_cid(self.dag.panel),
            protocol_params=artifact_cid(self.dag.params),
            rounds=rounds,
            verdict=artifact_cid(bad_verdict),
            supersedes=artifact_cid(pre_verdict),
        )
        problems = verify_manifest(root, self.store.as_resolver())
        self.assertTrue(any("finalRound" in p for p in problems), problems)

    def test_verdict_manifest_linkage_mismatch_detected(self) -> None:
        rounds = [artifact_cid(r) for r in self.dag.rounds]
        base = make_manifest(
            case_id="case-retry",
            question=artifact_cid(self.dag.question),
            evidence_ledger=artifact_cid(self.dag.ledger),
            panel=artifact_cid(self.dag.panel),
            protocol_params=artifact_cid(self.dag.params),
            rounds=rounds[:1],
        )
        self.store.put(base)
        pre_verdict = make_manifest(
            case_id="case-retry",
            question=artifact_cid(self.dag.question),
            evidence_ledger=artifact_cid(self.dag.ledger),
            panel=artifact_cid(self.dag.panel),
            protocol_params=artifact_cid(self.dag.params),
            rounds=rounds,
            supersedes=artifact_cid(base),
        )
        self.store.put(pre_verdict)
        bad_verdict = make_verdict(
            manifest=artifact_cid(base),  # wrong: must be the pre-verdict version
            final_round=rounds[-1],
            decision="d",
            recommendation="The Sovereign Conclave advises you to consider.",
            votes=[],
            confidence="low",
            issued_at="2026-10-01T10:05:00Z",
        )
        self.store.put(bad_verdict)
        root = make_manifest(
            case_id="case-retry",
            question=artifact_cid(self.dag.question),
            evidence_ledger=artifact_cid(self.dag.ledger),
            panel=artifact_cid(self.dag.panel),
            protocol_params=artifact_cid(self.dag.params),
            rounds=rounds,
            verdict=artifact_cid(bad_verdict),
            supersedes=artifact_cid(pre_verdict),
        )
        problems = verify_manifest(root, self.store.as_resolver())
        self.assertTrue(any("issued against" in p for p in problems), problems)

    def test_manifest_rounds_shrinking_detected(self) -> None:
        tampered = copy.deepcopy(self.dag.root)
        tampered["rounds"] = [artifact_cid(self.dag.rounds[1])]
        problems = verify_manifest(tampered, self.store.as_resolver())
        self.assertTrue(any("append-only" in p for p in problems), problems)


class TestRetrySupersedeSemantics(unittest.TestCase):
    def setUp(self) -> None:
        self.dag = SampleDag()
        self.store = Store()
        self.store.put(self.dag.question)
        self.store.put(self.dag.ledger)
        self.store.put(self.dag.panel)
        self.store.put(self.dag.params)
        for persona in self.dag.personas.values():
            self.store.put(persona)
        self.base_manifest = make_manifest(
            case_id="case-retry",
            question=artifact_cid(self.dag.question),
            evidence_ledger=artifact_cid(self.dag.ledger),
            panel=artifact_cid(self.dag.panel),
            protocol_params=artifact_cid(self.dag.params),
        )

    def _manifest(self, *,
                  rounds: list[Cid],
                  supersedes: Cid | None,
                  title: str) -> dict:
        manifest = make_manifest(
            case_id="case-retry",
            question=artifact_cid(self.dag.question),
            evidence_ledger=artifact_cid(self.dag.ledger),
            panel=artifact_cid(self.dag.panel),
            protocol_params=artifact_cid(self.dag.params),
            rounds=rounds,
            supersedes=supersedes,
            title=title,
        )
        self.store.put(manifest)
        return manifest

    def test_aborted_round_stays_in_dag_and_retry_supersedes_it(self) -> None:
        round0 = make_round(
            index=0,
            prev=None,
            status="committed",
            participants=["conclave-feynman", "conclave-marshall"],
            turns=[artifact_cid(t) for t in self.dag.turns[0][:1]],
            distilled_summary=artifact_cid(self.dag.summaries[0]),
            opened_at="2026-10-01T09:10:00Z",
        )
        aborted = make_round(
            index=1,
            prev=artifact_cid(round0),
            status="aborted",
            participants=["conclave-zhukov", "conclave-marshall"],
            opened_at="2026-10-01T09:41:00Z",
            failure_reason="orchestrator lost provider mid-round",
        )
        retry_turns = [
            make_turn(
                round_index=2,
                seat_id=seat_id,
                persona=artifact_cid(self.dag.personas[seat_id]),
                input_context_hash=raw_cid(f"prompt-retry-{seat_id}".encode()),
                model_id="claude-sonnet-4",
                temperature_micro=1_000_000,
                top_p_micro=1_000_000,
                max_output_tokens=4096,
                seed=7,
                output=raw_cid(f"output-retry-{seat_id}".encode()),
                citations=["E1", "E3"],
                tokens={"inputTokens": 900, "outputTokens": 340, "cacheReadTokens": 0},
                cost_micro_usd=4200,
                recorded_at="2026-10-01T09:43:00Z",
                provider_run=False,
            )
            for seat_id in ("conclave-zhukov", "conclave-marshall")
        ]
        retry_summary = make_summary(
            round_index=2,
            distilled_from=[artifact_cid(t) for t in retry_turns],
            positions=[
                {"seatId": "conclave-zhukov", "stance": "keep", "citations": ["E1", "E3"]},
                {"seatId": "conclave-marshall", "stance": "procedure-cleared", "citations": []},
            ],
            summary_text="Retry round gathered stances after the aborted attempt.",
            open_disagreements=["Zhukov still resists on E1 versus E3."],
            written_at="2026-10-01T09:44:00Z",
            model_id="haiku-class",
            word_count=44,
        )
        retry = make_round(
            index=2,
            prev=artifact_cid(aborted),
            status="committed",
            participants=["conclave-zhukov", "conclave-marshall"],
            turns=[artifact_cid(t) for t in retry_turns],
            distilled_summary=artifact_cid(retry_summary),
            supersedes=artifact_cid(aborted),
            opened_at="2026-10-01T09:42:00Z",
        )
        for artifact in (
            self.dag.turns[0][:1]
            + [self.dag.summaries[0]]
            + retry_turns
            + [retry_summary]
        ):
            self.store.put(artifact)
        for round_artifact in (round0, aborted, retry):
            self.store.put(round_artifact)
        manifest_v2 = self._manifest(
            rounds=[artifact_cid(round0), artifact_cid(aborted)],
            supersedes=artifact_cid(self.base_manifest),
            title="round 1 aborted, retry pending",
        )
        manifest_v3 = self._manifest(
            rounds=[artifact_cid(round0), artifact_cid(aborted), artifact_cid(retry)],
            supersedes=artifact_cid(manifest_v2),
            title="retry committed",
        )
        # Nothing deleted: the aborted round remains addressable and intact.
        resolved = self.store.get(artifact_cid(aborted))
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["status"], "aborted")
        self.assertEqual(
            resolved["failureReason"], "orchestrator lost provider mid-round"
        )
        self.assertEqual(verify_manifest(manifest_v3, self.store.as_resolver()), [])

    def test_superseding_a_committed_round_is_flagged(self) -> None:
        round0 = make_round(
            index=0,
            prev=None,
            status="committed",
            participants=["conclave-feynman", "conclave-marshall"],
            opened_at="2026-10-01T09:10:00Z",
        )
        round1 = make_round(
            index=1,
            prev=artifact_cid(round0),
            status="committed",
            participants=["conclave-zhukov", "conclave-marshall"],
            supersedes=artifact_cid(round0),  # illegal: round0 is committed
            opened_at="2026-10-01T09:41:00Z",
        )
        self.store.put(round0)
        self.store.put(round1)
        manifest = self._manifest(
            rounds=[artifact_cid(round0), artifact_cid(round1)],
            supersedes=artifact_cid(self.base_manifest),
            title="bad supersede probe",
        )
        problems = verify_manifest(manifest, self.store.as_resolver())
        self.assertTrue(any("only aborted rounds" in p for p in problems), problems)


class TestStruckTurns(unittest.TestCase):
    def test_struck_turn_kept_with_marshall_objection(self) -> None:
        dag = SampleDag()
        objection_holder = make_summary(
            round_index=1,
            distilled_from=[artifact_cid(t) for t in dag.turns[1]],
            positions=[{"seatId": "conclave-marshall", "stance": "objection", "citations": []}],
            summary_text="OBJECTION: struck turn cites E9, which is not in the frozen ledger.",
            open_disagreements=[],
            written_at="2026-10-01T09:44:00Z",
            model_id="haiku-class",
        )
        struck = make_turn(
            round_index=1,
            seat_id="conclave-washington",
            persona=artifact_cid(dag.personas["conclave-washington"]),
            input_context_hash=raw_cid(b"prompt-struck"),
            model_id="claude-sonnet-4",
            seed=None,
            output=raw_cid(b"output-struck"),
            citations=["E1"],
            struck=True,
            struck_reason="cited E9 which is absent from the frozen ledger",
            marshall_objection=artifact_cid(objection_holder),
            recorded_at="2026-10-01T09:44:30Z",
        )
        store = Store()
        store.put(objection_holder)
        store.put(struck)
        validate_artifact(struck)
        self.assertIs(struck["struck"], True)
        resolved = store.get(artifact_cid(struck))
        self.assertEqual(resolved["struckReason"], "cited E9 which is absent from the frozen ledger")
        self.assertIsNotNone(resolved["marshallObjection"])

    def test_struck_requires_objection_link(self) -> None:
        dag = SampleDag()
        with self.assertRaises(ArtifactError):
            make_turn(
                round_index=1,
                seat_id="conclave-washington",
                persona=artifact_cid(dag.personas["conclave-washington"]),
                input_context_hash=raw_cid(b"p"),
                model_id="claude-sonnet-4",
                seed=None,
                output=raw_cid(b"o"),
                citations=["E1"],
                struck=True,
                struck_reason="no objection linked",
                recorded_at="2026-10-01T09:45:00Z",
            )

    def test_citations_must_be_strings(self) -> None:
        dag = SampleDag()
        with self.assertRaises(ArtifactError):
            make_turn(
                round_index=2,
                seat_id="conclave-washington",
                persona=artifact_cid(dag.personas["conclave-washington"]),
                input_context_hash=raw_cid(b"p"),
                model_id="claude-sonnet-4",
                seed=None,
                output=raw_cid(b"o"),
                citations=["E1", 9],
                recorded_at="2026-10-01T09:45:00Z",
            )


if __name__ == "__main__":
    unittest.main()
