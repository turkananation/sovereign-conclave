"""Tests for the M4 cost model (integer micro-USD math) and its inputs."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (str(ROOT), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

import cost_estimator as ce  # noqa: E402
import provider_runner as pr  # noqa: E402
from conclave_core.cbor import encode  # noqa: E402


def rate(label: str = "t", inp: int = 1000, out: int = 3000, cr: int = 100, cw: int = 1250) -> ce.RateClass:
    return ce.RateClass(label, inp, out, cr, cw)


class ClassificationTests(unittest.TestCase):
    def test_builtin_substring_hints(self):
        self.assertEqual(ce.classify_model("fast-general"), "haiku")
        self.assertEqual(ce.classify_model("haiku-4"), "haiku")
        self.assertEqual(ce.classify_model("deep-reasoning"), "opus")
        self.assertEqual(ce.classify_model("verification-reasoning"), "opus")
        self.assertEqual(ce.classify_model("sonnet"), "sonnet")
        self.assertEqual(ce.classify_model("balanced-reasoning"), "sonnet")
        self.assertEqual(ce.classify_model("local-model"), "local")
        self.assertEqual(ce.classify_model("unknown-thing"), "sonnet")

    def test_exact_config_override_wins(self):
        rates = ce.rates_for(
            "fast-general",
            {"fast-general": {"input_usd_per_mtok_micro": 55, "output_usd_per_mtok_micro": 222,
                              "cache_read_usd_per_mtok_micro": 5, "cache_write_usd_per_mtok_micro": 60}},
        )
        self.assertEqual((rates.input, rates.output, rates.cache_read, rates.cache_write), (55, 222, 5, 60))
        # an unlisted family falls back to the builtin class table
        self.assertEqual(ce.rates_for("zzz-unknown", {}).label, "sonnet-class")


class CallCostTests(unittest.TestCase):
    def test_plain_call_is_floor_divided(self):
        # 3_000_000 input tokens x 1000 micro-USD/MTok = 3000 micro-USD exactly.
        row = ce.UsageRow({"inputTokens": 3_000_000, "outputTokens": 0, "cacheReadTokens": 0, "cacheWriteTokens": 0},
                          batch=False, estimated=False, model_id="m", subject_kind="turn")
        self.assertEqual(ce.call_cost_micro_usd(row, rate(inp=1000), use_cache=True), 3000)
        # floor division: 1 usual token below a full micro-USD rounds down
        self.assertEqual(ce.call_cost_micro_usd(
            ce.UsageRow({"inputTokens": 3_000_001, "outputTokens": 0, "cacheReadTokens": 0, "cacheWriteTokens": 0},
                        batch=False, estimated=False, model_id="m", subject_kind="turn"),
            rate(inp=1000), use_cache=True), 3000)

    def test_cache_semantics_billed_input_excludes_reads_and_writes(self):
        # inputTokens ALREADY includes cache read/write (provider semantics):
        # billed plain input = 2_000_000 - 1_500_000 - 100_000 = 400_000.
        row = ce.UsageRow(
            {"inputTokens": 2_000_000, "outputTokens": 0, "cacheReadTokens": 1_500_000, "cacheWriteTokens": 100_000},
            batch=False, estimated=False, model_id="m", subject_kind="turn",
        )
        rates = rate(inp=1000, cr=100, cw=1250)
        expected = 400 * 1 + 1500 * 0.1 + 100 * 1.25  # 400 + 150 + 125 = 675
        self.assertEqual(ce.call_cost_micro_usd(row, rates, use_cache=True), 675)

    def test_no_cache_reprices_reads_writes_at_full_input(self):
        row = ce.UsageRow(
            {"inputTokens": 2_000_000, "outputTokens": 0, "cacheReadTokens": 1_500_000, "cacheWriteTokens": 100_000},
            batch=False, estimated=False, model_id="m", subject_kind="turn",
        )
        rates = rate(inp=1000, cr=100, cw=1250)
        # everything at the plain input rate: 2_000_000 x 1000 / 1e6 = 2000
        self.assertEqual(ce.call_cost_micro_usd(row, rates, use_cache=False), 2000)

    def test_batch_discount_applies_only_to_batch_rows(self):
        base = {"inputTokens": 1_000_000, "outputTokens": 0, "cacheReadTokens": 0, "cacheWriteTokens": 0}
        batched = ce.UsageRow(base, batch=True, estimated=False, model_id="m", subject_kind="turn")
        self.assertEqual(ce.call_cost_micro_usd(batched, rate(inp=1000), use_cache=True), 500)
        interactive = ce.UsageRow(base, batch=False, estimated=False, model_id="m", subject_kind="turn")
        self.assertEqual(ce.call_cost_micro_usd(interactive, rate(inp=1000), use_cache=True), 1000)


class RowLoadingTests(unittest.TestCase):
    def test_transcript_json_estimates_from_chars(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "transcript.json"
            path.write_text(json.dumps({
                "calls": [
                    {"seat": "conclave-feynman", "prompt_chars": 4000, "prompt": "p" * 4000,
                     "response": "r" * 800, "model_family": "sonnet", "batch": False},
                    {"seat": "mechanical", "usage": {"inputTokens": 5000, "outputTokens": 300,
                                                     "cacheReadTokens": 4000, "cacheWriteTokens": 100},
                     "model_family": "fast-general", "batch": True, "prompt_parts": {"static": 3000, "dynamic": 100, "suffix": 900}},
                ]
            }), encoding="utf-8")
            rows = ce.load_rows(path)
        self.assertEqual(len(rows), 2)
        estimated, measured = rows
        self.assertTrue(estimated.estimated)
        self.assertEqual(estimated.tokens["inputTokens"], 1000)   # 4000 chars // 4
        self.assertEqual(estimated.tokens["outputTokens"], 200)   # 800 chars // 4
        self.assertFalse(measured.estimated)
        self.assertEqual(measured.tokens["inputTokens"], 5000)
        self.assertEqual(measured.batch, True)
        self.assertEqual(measured.input_parts, {"staticChars": 3000, "dynamicChars": 100, "suffixChars": 900})

    def test_bundle_dir_loads_telemetry_artifacts(self):
        from conclave_core.artifacts import make_question, make_telemetry, artifact_cid

        question = make_question("Should we restructure?", asked_by="test", asked_at="2026-01-01T00:00:00Z")
        telemetry = make_telemetry(
            subject=artifact_cid(question),
            subject_kind="round",
            tokens={"inputTokens": 100, "outputTokens": 20},
            model_id="sonnet",
            provider="anthropic",
            latency_ms=42,
            estimated=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            bundle = pathlib.Path(tmp) / "bundle"
            (bundle / "artifacts").mkdir(parents=True)
            (bundle / "artifacts" / "aaa.cbor").write_bytes(encode(telemetry))
            (bundle / "artifacts" / "zzz.cbor").write_bytes(encode({"type": "Question"}))
            rows = ce.load_rows(bundle)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].tokens, {"inputTokens": 100, "outputTokens": 20, "cacheReadTokens": 0, "cacheWriteTokens": 0})
        self.assertTrue(rows[0].estimated)


class ReportTests(unittest.TestCase):
    def test_report_ratios_and_exit_criterion(self):
        # Optimized: many cache reads at 0.1x; baseline: same journey at full price.
        def cached_row() -> ce.UsageRow:
            return ce.UsageRow(
                {"inputTokens": 1_000_000, "outputTokens": 100_000,
                 "cacheReadTokens": 900_000, "cacheWriteTokens": 0},
                batch=False, estimated=False, model_id="sonnet", subject_kind="turn",
            )

        rows = [cached_row() for _ in range(10)]
        report = ce.estimate(rows, {}, "sonnet")
        # optimized per call: plain 100_000x3000/1e6 = 300; read 900_000x300/1e6 = 270;
        # output 100_000x15000/1e6 = 1500 => 2070 micro-USD x 10 calls = 20700
        self.assertEqual(report["optimizedMicroUsd"], 20_700)
        # baseline per call: 1_000_000x3000/1e6 = 3000 input + 1500 output = 4500 x 10 = 45000
        self.assertEqual(report["baselineMicroUsd"], 45_000)
        self.assertEqual(report["optimizedVsBaselineMicroRatio"], 20_700 * 1_000_000 // 45_000)  # 460000
        self.assertFalse(report["meetsM4ExitCriterion"])  # 46% > 30%
        self.assertEqual(report["calls"], 10)
        self.assertEqual(report["estimatedCalls"], 0)

    def test_three_regimes_appear_in_per_call(self):
        row = ce.UsageRow(
            {"inputTokens": 1_000_000, "outputTokens": 10_000, "cacheReadTokens": 900_000, "cacheWriteTokens": 0},
            batch=True, estimated=False, model_id="fast-general", subject_kind="turn",
        )
        report = ce.estimate([row], {}, "sonnet")
        entry = report["perCall"][0]
        self.assertEqual(entry["modelId"], "fast-general")
        self.assertTrue(entry["batch"])
        # optimized: (100_000x80 + 900_000x8 + 10_000x400)/1e6 = (8000+7200+4000)=19200/1e6=19;
        # batched 19x0.5 => 9
        self.assertEqual(entry["optimizedMicroUsd"], 9)
        self.assertEqual(entry["baselineMicroUsd"], (1_000_000 * 3000 + 10_000 * 15_000) // 1_000_000)  # 3150

    def test_rates_report_lists_families(self):
        rates = ce.rates_report({}, ["fast-general", "sonnet"])
        self.assertEqual(rates["fast-general"]["class"], "haiku-class")
        self.assertEqual(rates["sonnet"]["class"], "sonnet-class")


if __name__ == "__main__":
    unittest.main()
