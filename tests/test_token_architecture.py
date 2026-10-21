"""Tests for the M4 prompt architecture: parts, caching, distillation, topology."""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (str(ROOT), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

import provider_runner as pr  # noqa: E402

JSON_SUMMARY = (
    '{"summaryText": "Split opinion on pacing.",'
    ' "positions": ['
    '{"seatId": "conclave-a", "stance": "Move fast with a flag", "citations": ["E1"]},'
    '{"seatId": "conclave-b", "stance": "Hold", "citations": []}],'
    ' "openDisagreements": ["a vs b: pace"]}'
)
JSON_CONSENSUS = '{"consensusScore": 90, "activeDissent": []}'


class StubClient:
    """Deterministic fake provider: sniff the task to mimic tiers."""

    name = "stub"

    def complete_parts(self, parts: pr.PromptParts, route: pr.Route, timeout: float):
        suffix = parts.persona_suffix
        if "round distiller" in suffix:
            return "prefix noise\n" + JSON_SUMMARY, pr.Usage(500, 80, 400, 100)
        if "consensus scorer" in suffix:
            return JSON_CONSENSUS, pr.Usage(300, 20, 300, 0)
        if seat := _seat_of(suffix):
            return f"[{seat}] position.", None
        return "[terminal] response.", None


def _seat_of(suffix: str) -> str | None:
    for seat in ("conclave-a", "conclave-b", "conclave-c", "conclave-d"):
        if seat in suffix:
            return seat
    return None


def roster(seats: list[str], kind: str = "advocate") -> dict[str, dict]:
    return {seat: {"id": seat, "lens": f"lens-{seat}", "model": "sonnet", "type": kind} for seat in seats}


class PromptPartsTests(unittest.TestCase):
    def test_assemble_joins_segments_byte_exact(self):
        parts = pr.PromptParts("STATIC", "DYNAMIC", "SUFFIX")
        self.assertEqual(parts.assemble(), "STATICDYNAMICSUFFIX")
        self.assertEqual(len(parts.assemble()),
                         len(parts.static_prefix) + len(parts.dynamic_middle) + len(parts.persona_suffix))

    def test_dynamic_middle_uses_distilled_records_then_falls_back(self):
        record = pr.RoundRecord(index=0, kind="opening",
                                responses=[("conclave-a", "A text")],
                                summary={"summaryText": "digest", "positions": [
                                    {"seatId": "conclave-a", "stance": "stance", "citations": ["E1"]}],
                                    "openDisagreements": ["a: x"]},
                                consensus=None)
        dynamic = pr.build_dynamic_middle([record])
        self.assertIn("ROUND 0 (opening) — distilled record:", dynamic)
        self.assertIn("Summary: digest", dynamic)
        self.assertIn("- conclave-a: stance [E1]", dynamic)
        self.assertNotIn("Consensus score:", dynamic)
        with_consensus = pr.build_dynamic_middle([
            pr.RoundRecord(
                index=0, kind="opening", responses=[("conclave-a", "A text")],
                summary=record.summary,
                consensus={"consensusScore": 88, "activeDissent": ["conclave-b"]},
            )
        ])
        self.assertIn("Consensus score: 88/100", with_consensus)
        self.assertIn("active dissent: conclave-b", with_consensus)
        # degraded: no summary → verbatim fallback
        degraded = pr.build_dynamic_middle([pr.RoundRecord(index=0, kind="opening",
                                                          responses=[("conclave-a", "A verbatim")])])
        self.assertIn("distillation failed", degraded)
        self.assertIn("[conclave-a]\nA verbatim", degraded)

    def test_anthropic_body_has_two_cache_breakpoints(self):
        client = pr.AnthropicClient(api_key="k", model="claude-test")
        body = client._build_body(pr.PromptParts("S", "D", "X"))
        self.assertEqual(body["system"][0]["cache_control"], {"type": "ephemeral"})
        blocks = body["messages"][0]["content"]
        self.assertEqual(blocks[0]["text"], "D")
        self.assertEqual(blocks[0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(blocks[1]["text"], "X")
        self.assertNotIn("cache_control", blocks[1])
        usage = client._parse_usage({"usage": {"input_tokens": 10, "output_tokens": 2,
                                               "cache_read_input_tokens": 7, "cache_creation_input_tokens": 3}})
        self.assertEqual((usage.input_tokens, usage.output_tokens, usage.cache_read_tokens,
                          usage.cache_write_tokens), (10, 2, 7, 3))
        missing = client._parse_usage({"usage": {}})
        self.assertEqual((missing.input_tokens, missing.output_tokens), (0, 0))


class DistillerParsingTests(unittest.TestCase):
    def test_parse_distillation_normalizes(self):
        payload = pr.parse_distillation("junk\n```json\n" + JSON_SUMMARY + "\n```")
        self.assertEqual(payload["summaryText"], "Split opinion on pacing.")
        self.assertEqual(payload["positions"][0], {"seatId": "conclave-a", "stance": "Move fast with a flag",
                                                   "citations": ["E1"]})
        self.assertEqual(payload["openDisagreements"], ["a vs b: pace"])

    def test_parse_distillation_negatives(self):
        for bad in (
            "no json here",
            "{not json}",
            '{"summaryText": "s", "positions": []}',
            '{"positions": [{"seatId": "a", "stance": "s"}]}',
            '{"summaryText": "", "positions": [{"seatId": "a", "stance": "s"}]}',
            '{"summaryText": "s", "positions": [{"seatId": "", "stance": "s"}]}',
            '{"summaryText": "s", "positions": "nope"}',
        ):
            self.assertIsNone(pr.parse_distillation(bad), msg=bad)

    def test_parse_consensus_and_gate(self):
        self.assertEqual(pr.parse_consensus('{"consensusScore": 92, "activeDissent": []}'),
                         {"consensusScore": 92, "activeDissent": []})
        # bool is not an int score; ints clamp to 0..100
        self.assertIsNone(pr.parse_consensus('{"consensusScore": true, "activeDissent": []}'))
        self.assertEqual(pr.parse_consensus('{"consensusScore": 400, "activeDissent": "x"}'),
                         {"consensusScore": 100, "activeDissent": []})
        self.assertIsNone(pr.parse_consensus("nope"))
        gate = pr.consensus_reached({"consensusScore": 90, "activeDissent": []}, 85)
        self.assertTrue(gate)
        dissent = pr.consensus_reached({"consensusScore": 99, "activeDissent": ["conclave-a"]}, 85)
        self.assertFalse(dissent)
        below = pr.consensus_reached({"consensusScore": 84, "activeDissent": []}, 85)
        self.assertFalse(below)
        self.assertFalse(pr.consensus_reached(None, 85))


class CommitteeTopologyTests(unittest.TestCase):
    def test_committees_engage_only_for_large_panels(self):
        small = [f"s{i}" for i in range(6)]
        self.assertIsNone(pr.committees_for(small, 3))
        large = [f"s{i}" for i in range(10)]
        committees = pr.committees_for(large, 3)
        self.assertEqual(committees, [["s0", "s1", "s2"], ["s3", "s4", "s5"],
                                      ["s6", "s7", "s8"], ["s9"]])  # ordered chunks, small tail
        self.assertIsNone(pr.committees_for(large, 0))  # explicitly disabled

    def test_committee_plan_shape_and_alignment(self):
        advocates = [f"s{i}" for i in range(10)]
        committees = pr.committees_for(advocates, 3)
        plans = pr.plan_rounds(advocates, committees, rounds=4)
        kinds = [plan.kind for plan in plans]
        self.assertEqual(kinds, ["opening", "committee", "cross-committee", "full-council"])
        self.assertEqual([plan.index for plan in plans], [0, 1, 2, 3])
        # every plan's suffix list aligns with its attendees
        for plan in plans:
            self.assertEqual(len(plan.attendees), len(plan.suffixes))
        opening, committee, cross, council = plans
        self.assertEqual(opening.attendees, advocates)  # blind round includes everyone
        delegates = [c[0] for c in committees]
        self.assertEqual(committee.attendees, delegates)
        # cross: each committee attacks each other committee exactly once, no self-attacks
        self.assertEqual(len(cross.attendees), 4 * 3)
        for attacker, instruction in zip(cross.attendees, cross.suffixes):
            self.assertIn("Attack the distilled position of seat", instruction)
            self.assertTrue(attacker.startswith("s"))
        # full-council reconvenes the delegates
        self.assertEqual(council.attendees, delegates)

    def test_committee_plan_truncates_to_round_budget(self):
        advocates = [f"s{i}" for i in range(10)]
        committees = pr.committees_for(advocates, 3)
        plans = pr.plan_rounds(advocates, committees, rounds=2)
        self.assertEqual([plan.kind for plan in plans], ["opening", "committee"])
        small = [f"s{i}" for i in range(4)]
        plans = pr.plan_rounds(small, None, rounds=3)
        self.assertEqual([plan.kind for plan in plans], ["opening", "challenge", "challenge"])
        single = pr.plan_rounds(advocates, committees, rounds=1)
        self.assertEqual([plan.kind for plan in single], ["opening"])

    def test_cross_attackers_have_distinct_speaking_slots(self):
        # duplicate attendees (same attacker, several targets) keep per-target suffixes
        advocates = [f"s{i}" for i in range(7)]
        committees = pr.committees_for(advocates, 3)  # 3 committees: [s0..2][s3..5][s6]
        cross = next(p for p in pr.plan_rounds(advocates, committees, rounds=3) if p.kind == "cross-committee")
        self.assertEqual(len(cross.attendees), 3 * 2)
        self.assertEqual(len(set(cross.attendees)), 3)  # one attacker voice per committee


class RunDeliberationFlowTests(unittest.TestCase):
    def setUp(self):
        self.cfg = pr.parse_provider_config("")

    def _run(self, seats=("conclave-a", "conclave-b"), rounds=1, committee_size=7):
        convened = list(seats) + ["conclave-marshall"]
        lookup = roster(list(seats))
        lookup["conclave-marshall"] = roster(["conclave-marshall"], "verifier")["conclave-marshall"]
        return pr.run_deliberation(
            convened=convened,
            seat_lookup=lookup,
            agent_text=lambda seat: f"persona({seat})",
            provider_cfg=self.cfg,
            client=StubClient(),
            problem="Question?",
            ledger_section="E1: some evidence",
            timeout=5,
            options=pr.RunOptions(rounds=rounds, committee_size=committee_size),
        )

    def test_single_round_flow_makes_one_distill_and_no_consensus(self):
        result = self._run(rounds=1)
        roles = [record["role"] for record in result.transcript]
        self.assertEqual(roles.count("round"), 2)
        self.assertEqual(roles.count("distill"), 1)
        self.assertNotIn("consensus", roles)
        self.assertEqual(roles.count("verification"), 1)
        self.assertEqual(result.errors, 0)
        self.assertIsNone(result.early_exit_round)
        self.assertEqual(result.rounds[0].summary["summaryText"], "Split opinion on pacing.")
        # static prefix byte-identical across every call in the run
        static_lengths = {record["prompt_parts"]["static"] for record in result.transcript}
        self.assertEqual(len(static_lengths), 1)
        static_length = static_lengths.pop()
        statics = {record["prompt"][:static_length] for record in result.transcript}
        self.assertEqual(len(statics), 1)
        self.assertIn("EVIDENCE LEDGER (frozen before Round 1):", statics.pop())

    def test_early_exit_skips_later_rounds(self):
        seats = ("conclave-a", "conclave-b")
        result = self._run(seats=seats, rounds=3)
        roles = [record["role"] for record in result.transcript]
        self.assertEqual(roles.count("round"), 2)  # opening only; exit after round 0 consensus
        self.assertEqual(roles.count("consensus"), 1)
        self.assertEqual(result.early_exit_round, 0)
        self.assertEqual(result.rounds[0].consensus, {"consensusScore": 90, "activeDissent": []})

    def test_multi_round_continues_without_consensus(self):
        seats = ("conclave-a", "conclave-b")
        original = pr.parse_consensus
        pr.parse_consensus = lambda text: {"consensusScore": 10, "activeDissent": ["conclave-b"]}
        try:
            result = self._run(seats=seats, rounds=3, committee_size=0)
        finally:
            pr.parse_consensus = original
        rounds = [record["role"] for record in result.transcript].count("round")
        self.assertEqual(rounds, 2 * 3)  # 2 seats x 3 rounds
        self.assertIsNone(result.early_exit_round)
        self.assertEqual({kind for kind in (r.kind for r in result.rounds)}, {"opening", "challenge"})

    def test_error_call_counts_and_marks_failed_transcript(self):
        class ExplodingClient(StubClient):
            name = "stub"

            def complete_parts(self, parts, route, timeout):
                raise RuntimeError("boom")

        result = pr.run_deliberation(
            convened=["conclave-a"],
            seat_lookup=roster(["conclave-a"]),
            agent_text=lambda seat: "p",
            provider_cfg=pr.parse_provider_config(""),
            client=ExplodingClient(),
            problem="q",
            ledger_section="E1",
            timeout=5,
        )
        # every call in the run fails and each failure is recorded, not fatal
        self.assertEqual(result.errors, len(result.transcript))
        self.assertEqual(result.errors, 3)  # advocate + distill + synthesis
        failed = [record for record in result.transcript if not record["ok"]]
        self.assertEqual(len(failed), 3)
        self.assertIn("boom", failed[0]["error"])
        self.assertIn("[provider error", failed[0]["response"])


if __name__ == "__main__":
    unittest.main()
