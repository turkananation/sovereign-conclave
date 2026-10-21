"""M6 orchestrator tests: FSM runs, budget degradation ladder, kill/resume."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "scripts"), str(ROOT / "tests")):
    if path not in sys.path:
        sys.path.insert(0, path)

from conclave_core.artifacts import artifact_cid, make_protocol_params, utc_now  # noqa: E402
from conclave_core.merkle import tree_hash  # noqa: E402
from conclave_core.verifier import verify_bundle  # noqa: E402
from conclave_server.materialize import materialize_case  # noqa: E402
from conclave_server.orchestrator import CaseRun, ConveneRequest, SeatClient  # noqa: E402
from conclave_server.sessions import SessionHub  # noqa: E402
from conclave_server.store import ArtifactStore  # noqa: E402
from test_emit_bundle import LEDGER_ENTRIES, ROSTER  # canonical emit fixtures

ADVOCATES = ("conclave-feynman", "conclave-zhukov")
MARSHALL = "conclave-marshall"

SUMMARY_TEMPLATE = (
    '{{"summaryText": "Round {round_index} distilled cleanly.", "positions": '
    '[{{"seatId": "conclave-feynman", "stance": "proceed", "citations": ["E1"]}}, '
    '{{"seatId": "conclave-zhukov", "stance": "proceed", "citations": ["E1"]}}], '
    '"openDisagreements": []}}'
)


def consensus_payload(score: int, dissent: list[str]) -> str:
    return json.dumps({"consensusScore": score, "activeDissent": dissent})


class StubClient(SeatClient):
    """Deterministic seat calls with per-round consensus configuration."""

    def __init__(self, consensus_by_round=None, tokens=(10, 20)) -> None:
        self.calls: list[tuple[str, str]] = []
        self.consensus_by_round = consensus_by_round or {}
        self._input_tokens, self._output_tokens = tokens

    def call(self, seat_id, role, round_index, round_kind, prompt):
        self.calls.append((seat_id, role, round_index))
        if role == "round":
            return {
                "response": (
                    f"Position from {seat_id} for round {round_index} ({round_kind}). "
                    "Cites E1; the ledger supports the recorded direction. "
                    "confidence: high"
                ),
                "model_family": ROSTER_SEATS.get(seat_id, {}).get("model", "stub"),
                "provider": "stub",
                "slot": "stub",
                "usage": {
                    "inputTokens": self._input_tokens,
                    "outputTokens": self._output_tokens,
                    "cacheReadTokens": 0,
                    "cacheWriteTokens": 0,
                },
                "elapsed_s": 0.01,
            }
        if role == "distill":
            return {
                "response": SUMMARY_TEMPLATE.format(round_index=round_index),
                "model_family": "distiller",
                "provider": "stub",
                "usage": None,
                "elapsed_s": 0.005,
            }
        if role == "consensus":
            score, dissent = self.consensus_by_round.get(
                round_index, (90, [])
            )
            return {
                "response": consensus_payload(score, dissent),
                "model_family": "scorer",
                "provider": "stub",
                "usage": None,
                "elapsed_s": 0.005,
            }
        raise AssertionError(f"unexpected role: {role}")


class KillAfterCallsClient(StubClient):
    """Stub that raises once it has served its allowed call budget."""

    def __init__(self, max_calls: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.max_calls = max_calls

    def call(self, *args, **kwargs):
        if len(self.calls) >= self.max_calls:
            raise RuntimeError("provider killed mid-run")
        return super().call(*args, **kwargs)


ROSTER_SEATS = {seat["id"]: seat for seat in ROSTER["seats"]}


class OrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = ArtifactStore(self.root / "store.sqlite3")
        self.hub = SessionHub()

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def _request(self, *, profile_id="architecture", problem="Adopt variant B?", budget=None,
                 params=None, timestamp="2026-10-21T09:00:00Z", seats=ADVOCATES) -> ConveneRequest:
        return ConveneRequest(
            profile_id=profile_id,
            problem=problem,
            roster=ROSTER,
            seats=list(seats),
            marshall_id=MARSHALL,
            ledger_entries=LEDGER_ENTRIES,
            token_budget=budget,
            protocol_params=params,
            timestamp=timestamp,
        )

    def _new_run(self, client) -> CaseRun:
        run = CaseRun(self.store, self.hub, self.root / "keys", client)
        return run

    def _convened_run(self, client, **request_kwargs) -> CaseRun:
        run = self._new_run(client)
        run.convene(self._request(**request_kwargs))
        return run

    def test_single_session_full_run_streams_events_and_closes(self):
        client = StubClient()
        run = self._convened_run(client)
        run.drive()

        case_ref = run.case_ref
        self.assertTrue(case_ref.startswith("case-architecture-"))
        result = run.result()
        self.assertIn("verdictCid", result)

        kinds = [event["kind"] for event in self.hub.events(case_ref)]
        self.assertEqual(
            kinds,
            ["convened", "round-started", "turn-committed", "turn-committed",
             "turn-committed", "summary", "consensus-score", "verdict", "closed"],
        )
        self.assertEqual(client.calls[:3], [
            (ADVOCATES[0], "round", 0),
            (ADVOCATES[1], "round", 0),
            (MARSHALL, "round", 0),
        ])

        self.assertEqual(len(self.store.by_type("Turn")), 3)
        self.assertEqual(len(self.store.by_type("Round")), 1)
        self.assertEqual(len(self.store.by_type("Summary")), 1)
        self.assertEqual(len(self.store.by_type("DeliberationManifest")), 3)  # open/rounds/final
        self.assertEqual(len(self.store.by_type("Telemetry")), 5)  # 3 turns + distill + consensus
        self.assertEqual(len(self.store.by_type("Verdict")), 1)

        verdict = self.store.by_type("Verdict")[0]
        artifact = self.store.get(verdict)
        self.assertEqual(len(artifact["votes"]), 2)
        self.assertTrue(
            artifact["recommendation"].startswith("The Sovereign Conclave advises")
        )

        manifest = self.store.get(
            next(cid for cid in self.store.by_type("DeliberationManifest")
                 if self.store.get(cid)["verdict"])
        )
        self.assertEqual(len(manifest["rounds"]), 1)
        self.assertEqual(str(manifest["verdict"]), str(verdict))

        # payloads stay resolvable: every turn output has its raw bytes
        for cid in self.store.by_type("Turn"):
            output_cid = str(self.store.get(cid)["output"])
            self.assertIsNotNone(self.store.payload(f"{output_cid}.raw"))

        leaves = self.store.leaves(case_ref)
        self.assertEqual(leaves, [verdict])
        heads = self.store.heads(case_ref)
        self.assertEqual([head[0] for head in heads], [1])
        self.assertEqual(heads[0][1], tree_hash([verdict.cid_bytes()]))

        state_row = self.store.session(case_ref)
        self.assertEqual(state_row and json.loads(state_row["position"]), ["closed"])
        self.assertEqual(run.session_state.phase, "closed")

    def test_consensus_early_exit_skips_later_rounds(self):
        params = make_protocol_params(quorum=3, max_rounds=4, early_exit_threshold_pct=85,
                                      recorded_by="session-orchestrator")
        client = StubClient()
        run = self._convened_run(client, params=params)
        run.drive()

        # every call stayed in round 0 (the early exit skipped challenge rounds)
        self.assertEqual({c[-1] for c in client.calls}, {0})
        self.assertEqual(len(client.calls), 5)  # 3 seats + distill + consensus
        self.assertEqual(len(self.store.by_type("Round")), 1)
        verdict = self.store.get(self.store.by_type("Verdict")[0])
        self.assertEqual(len(verdict["votes"]), 2)

    def test_budget_ladder_batch_then_tighten(self):
        # round 0 spends 150 (5 calls x 30 tokens); budget 140 triggers the
        # batch rung at the round-1 entry, then the tighten rung at round 2
        params = make_protocol_params(quorum=3, max_rounds=3, early_exit_threshold_pct=1,
                                      recorded_by="session-orchestrator")
        client = StubClient(consensus_by_round={0: (40, ["conclave-zhukov"]),
                                                1: (35, ["conclave-zhukov"]),
                                                2: (30, ["conclave-zhukov"])})
        run = self._convened_run(client, budget=140, params=params)
        run.drive()

        self.assertEqual(len(self.store.by_type("Round")), 3)
        self.assertEqual(run.session_state.degraded, ["batch", "tighten-sparse-topology"])

        degraded_events = [e for e in self.hub.events(run.case_ref) if e["kind"] == "degraded"]
        self.assertEqual([e["payload"]["rung"] for e in degraded_events],
                         ["batch", "tighten-sparse-topology"])

        # round 2 convened the tightened topology: keep = ceil(2 / 2) = 1 advocate
        rounds = sorted(self.store.by_type("Round"), key=lambda c: self.store.get(c)["index"])
        second = self.store.get(rounds[-1])
        self.assertEqual(second["participants"], [ADVOCATES[0], MARSHALL])
        self.assertEqual(len([c for c in self.store.by_type("Turn")
                              if self.store.get(c)["roundIndex"] == 2]), 2)

        manifest = next(
            self.store.get(c) for c in self.store.by_type("DeliberationManifest")
            if len(self.store.get(c)["rounds"]) == 3 and not self.store.get(c)["verdict"]
        )
        self.assertIn("degradation ladder applied", str(manifest.get("note")))

        batched = [
            self.store.get(cid)
            for cid in self.store.by_type("Telemetry")
            if self.store.get(cid)["batch"]
        ]
        self.assertGreaterEqual(len(batched), 9)  # round 1 onward: 5 calls + 2 telemetries/round

    def test_budget_ladder_reaches_early_verdict(self):
        params = make_protocol_params(quorum=3, max_rounds=5, early_exit_threshold_pct=1,
                                      recorded_by="session-orchestrator")
        client = StubClient(consensus_by_round={r: (40, ["conclave-zhukov"]) for r in range(5)})
        run = self._convened_run(client, budget=80, params=params)
        run.drive()

        self.assertEqual(
            run.session_state.degraded,
            ["batch", "tighten-sparse-topology", "early-verdict-reduced-rounds"],
        )
        result = run.result()
        self.assertIn("verdictCid", result)
        # the reduced-rounds rung cut the plan before max_rounds rounds could finish
        self.assertLess(len(self.store.by_type("Round")), 5)

    def test_dissent_files_dissent_artifact_and_auto_t3(self):
        # two advocates with one dissenter => weight share 1/3 >= 30% => auto T3
        # threshold 1 + recorded dissent on every round keeps the conclave until it closes
        params = make_protocol_params(quorum=3, max_rounds=4, early_exit_threshold_pct=1,
                                      recorded_by="session-orchestrator")
        client = StubClient(
            consensus_by_round={r: (40, ["conclave-zhukov"]) for r in range(4)}
        )
        run = self._convened_run(client, params=params)
        run.drive()

        result = run.result()
        self.assertEqual(len(result["dissentCids"]), 1)
        self.assertIn("appealCid", result)
        dissent = self.store.get(parse_cid(result["dissentCids"][0]))
        self.assertEqual(dissent["seatId"], "conclave-zhukov")
        self.assertIn("E1", dissent["citedLedgerIds"])

        appeal = self.store.get(parse_cid(result["appealCid"]))
        self.assertEqual(appeal["trigger"], "T3")
        self.assertTrue(appeal["filedBy"].startswith("mechanical:T3"))
        leaves = self.store.leaves(run.case_ref)
        self.assertEqual(len(leaves), 2)
        self.assertEqual([str(leaf) for leaf in leaves],
                         [result["verdictCid"], result["appealCid"]])

    def test_kill_resume_mid_round_completes_clean(self):
        params = make_protocol_params(quorum=3, max_rounds=2, early_exit_threshold_pct=1,
                                      recorded_by="session-orchestrator")
        killer = KillAfterCallsClient(
            max_calls=5, consensus_by_round={0: (40, ["conclave-zhukov"]), 1: (40, ["conclave-zhukov"])}
        )
        run = self._convened_run(killer, params=params)
        # round 0 commits 5 calls; the 6th call (round 1's first seat) kills
        with self.assertRaises(RuntimeError):
            run.drive()

        row = self.store.session(run.case_ref)
        self.assertIsNotNone(row)
        self.assertEqual(json.loads(row["position"]), ["round", 1, "turn", 0])
        pre_kill_tokens = int(row["tokens_used"])
        self.assertGreater(pre_kill_tokens, 90)  # at least the three recorded seat calls

        resumed = CaseRun(self.store, self.hub, self.root / "keys", StubClient())
        resumed.resume(run.case_ref)
        self.assertEqual(resumed.session_state.tokens_used, pre_kill_tokens)
        resumed.drive()

        result = resumed.result()
        self.assertIn("verdictCid", result)
        # no orphan turns: the killed call never committed; the same seat runs once
        self.assertEqual(len(self.store.by_type("Turn")), 6)  # 3 seats x 2 rounds
        self.assertEqual(resumed.session_state.phase, "closed")
        self.assertGreater(resumed.session_state.tokens_used, pre_kill_tokens)

    def test_materialized_case_verifies_clean(self):
        client = StubClient()
        run = self._convened_run(client)
        run.drive()
        result = run.result()

        bundle = materialize_case(self.store, self.root / "keys", run.case_ref,
                                  self.root / "bundle")
        problems, summary = verify_bundle(bundle)
        self.assertEqual(problems, [], summary)

    def test_materialized_t3_case_verifies_clean(self):
        params = make_protocol_params(quorum=3, max_rounds=4, early_exit_threshold_pct=1,
                                      recorded_by="session-orchestrator")
        client = StubClient(
            consensus_by_round={r: (40, ["conclave-zhukov"]) for r in range(4)}
        )
        run = self._convened_run(client, params=params)
        run.drive()
        self.assertIn("appealCid", run.result())

        bundle = materialize_case(self.store, self.root / "keys", run.case_ref,
                                  self.root / "bundle")
        problems, summary = verify_bundle(bundle)
        self.assertEqual(problems, [], summary)

    def test_materialized_resumed_case_verifies_clean(self):
        params = make_protocol_params(quorum=3, max_rounds=2, early_exit_threshold_pct=1,
                                      recorded_by="session-orchestrator")
        killer = KillAfterCallsClient(
            max_calls=5, consensus_by_round={0: (40, ["conclave-zhukov"]), 1: (40, ["conclave-zhukov"])}
        )
        run = self._convened_run(killer, params=params)
        with self.assertRaises(RuntimeError):
            run.drive()

        resumed = CaseRun(self.store, self.hub, self.root / "keys", StubClient())
        resumed.resume(run.case_ref)
        resumed.drive()
        self.assertEqual(resumed.session_state.phase, "closed")

        bundle = materialize_case(self.store, self.root / "keys", run.case_ref,
                                  self.root / "bundle")
        problems, summary = verify_bundle(bundle)
        self.assertEqual(problems, [], summary)

    def test_two_concurrent_sessions_isolate(self):
        results = {}
        errors = {}

        def run_case(name: str, stamp: str) -> None:
            try:
                client = StubClient()
                run = CaseRun(self.store, self.hub, self.root / "keys", client)
                run.convene(self._request(profile_id=name, timestamp=stamp))
                run.drive()
                results[name] = run.result()
            except Exception as exc:  # pragma: no cover - surfaced by the assert
                errors[name] = exc

        threads = [
            threading.Thread(target=run_case, args=(*pair,))
            for pair in [("alpha", "2026-10-21T09:00:00Z"), ("beta", "2026-10-22T10:30:00Z")]
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(errors, {})
        self.assertEqual(set(results), {"alpha", "beta"})
        self.assertNotEqual(results["alpha"]["verdictCid"], results["beta"]["verdictCid"])
        for case_ref in (self.store.session_refs()):
            self.assertEqual(json.loads(self.store.session(case_ref)["position"]), ["closed"])


def parse_cid(cid_str: str):
    from conclave_core.cid import parse
    return parse(cid_str)


if __name__ == "__main__":
    unittest.main()
