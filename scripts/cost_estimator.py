#!/usr/bin/env python3
"""Cost model for the M4 token architecture (roadmap axis 8).

Reads one or more case bundles (Telemetry artifacts) or provider transcripts
and prices them three ways with integer micro-USD arithmetic:

- ``optimized``      — what the run actually billed: cascade tiers, prompt-cache
                       discounts (cache reads ~0.1x, writes ~1.25x) and the
                       flat 0.5x batch discount on batch-marked calls,
- ``uncached``       — the same call plan without cache benefits (prompt caching
                       OFF, cascade kept),
- ``baseline``       — no cache AND no cascade: every call priced at one
                       reference family (default sonnet-class), i.e. the v0.1
                       style single-model deliberation.

The ratio ``optimized / baseline`` is the number the M4 exit criterion bounds
(<=30%). Arithmetic is exact integer micro-USD per million tokens; nothing in
an artifact is ever a float. When a client could not report usage, tokens were
character-estimated (telemetry ``estimated`` = true, ~4 chars/token) — the
report states the estimated share.

Pricing rates resolve per ``modelFamily``: an exact match from the provider
config's ``pricing`` section wins; otherwise families are classified by
substring into the builtin rate classes (haiku/local/sonnet/opus). Builtin
rates are documented approximations of public list prices; operators should
override them for their contracts.

Fidelity note (roadmap M4): distillation-fidelity spot audits are a procedural
process — a second, stronger pass reviews distiller summaries against the raw
turns and may file ``fidelityObjections``; see demos/benchmarks/README.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from conclave_core.cbor import decode  # noqa: E402

BATCH_DISCOUNT_MICRO = 500_000  # flat 0.5x applied as micro-multiplier 500000/1000000


@dataclass(frozen=True)
class RateClass:
    """Integer micro-USD per million tokens."""

    label: str
    input: int
    output: int
    cache_read: int
    cache_write: int


BUILTIN_RATE_CLASSES = {
    "haiku": RateClass("haiku-class", 80, 400, 8, 100),
    "opus": RateClass("opus-class", 15_000, 75_000, 1_500, 18_750),
    "sonnet": RateClass("sonnet-class", 3_000, 15_000, 300, 3_750),
    "local": RateClass("local (self-hosted)", 0, 0, 0, 0),
}

# First matching substring wins; families like "fast-general" (mechanical tier)
# classify to haiku-class, "deep-reasoning"/"verif*" to opus-class.
MODEL_HINTS = (
    ("fast", "haiku"),
    ("haiku", "haiku"),
    ("local", "local"),
    ("deep", "opus"),
    ("verif", "opus"),
    ("opus", "opus"),
    ("balanced", "sonnet"),
    ("sonnet", "sonnet"),
)

PRICING_KEYS = (
    "input_usd_per_mtok_micro",
    "output_usd_per_mtok_micro",
    "cache_read_usd_per_mtok_micro",
    "cache_write_usd_per_mtok_micro",
)


def classify_model(model_id: str) -> str:
    lowered = (model_id or "").lower()
    for hint, rate_key in MODEL_HINTS:
        if hint in lowered:
            return rate_key
    return "sonnet"


def rates_for(model_id: str, exact_rates: dict[str, dict[str, int]]) -> RateClass:
    explicit = exact_rates.get(model_id)
    if explicit:
        return RateClass(
            label=model_id,
            input=explicit.get("input_usd_per_mtok_micro", 0),
            output=explicit.get("output_usd_per_mtok_micro", 0),
            cache_read=explicit.get("cache_read_usd_per_mtok_micro", 0),
            cache_write=explicit.get("cache_write_usd_per_mtok_micro", 0),
        )
    return BUILTIN_RATE_CLASSES[classify_model(model_id)]


@dataclass(frozen=True)
class UsageRow:
    tokens: dict[str, int]
    batch: bool
    estimated: bool
    model_id: str
    subject_kind: str
    input_parts: dict[str, int] | None = None


def row_from_telemetry(telemetry: dict) -> UsageRow:
    parts = telemetry.get("inputParts")
    return UsageRow(
        tokens={
            "inputTokens": int(telemetry["tokens"].get("inputTokens", 0)),
            "outputTokens": int(telemetry["tokens"].get("outputTokens", 0)),
            "cacheReadTokens": int(telemetry["tokens"].get("cacheReadTokens", 0)),
            "cacheWriteTokens": int(telemetry["tokens"].get("cacheWriteTokens", 0)),
        },
        batch=bool(telemetry.get("batch", False)),
        estimated=bool(telemetry.get("estimated", False)),
        model_id=str(telemetry.get("modelId", "")),
        subject_kind=str(telemetry.get("subjectKind", "")),
        input_parts={key: int(parts[key]) for key in ("staticChars", "dynamicChars", "suffixChars")} if parts else None,
    )


def row_from_transcript_record(record: dict[str, Any]) -> UsageRow:
    usage = record.get("usage")
    if usage is not None:
        tokens = {
            "inputTokens": int(usage.get("inputTokens", 0) or 0),
            "outputTokens": int(usage.get("outputTokens", 0) or 0),
            "cacheReadTokens": int(usage.get("cacheReadTokens", 0) or 0),
            "cacheWriteTokens": int(usage.get("cacheWriteTokens", 0) or 0),
        }
        estimated = False
    else:
        estimated = True
        prompt_chars = record.get("prompt_chars")
        prompt_chars = (
            int(prompt_chars) if prompt_chars is not None else len(str(record.get("prompt", "")))
        )
        tokens = {
            "inputTokens": prompt_chars // 4,
            "outputTokens": len(str(record.get("response", ""))) // 4,
            "cacheReadTokens": 0,
            "cacheWriteTokens": 0,
        }
    parts = record.get("prompt_parts")
    input_parts = (
        {
            "staticChars": int(parts.get("static", parts.get("staticChars", 0))),
            "dynamicChars": int(parts.get("dynamic", parts.get("dynamicChars", 0))),
            "suffixChars": int(parts.get("suffix", parts.get("suffixChars", 0))),
        }
        if parts
        else None
    )
    return UsageRow(
        tokens=tokens,
        batch=bool(record.get("batch", False)),
        estimated=estimated,
        model_id=str(record.get("model_family", "")),
        subject_kind="turn" if record.get("seat") != "mechanical" else "mechanical",
        input_parts=input_parts,
    )


def _token_part_micro(tokens: int, rate_per_mtok: int) -> int:
    # floor division keeps us conservative: never over-bill an estimate
    return tokens * rate_per_mtok // 1_000_000


def call_cost_micro_usd(row: UsageRow, rates: RateClass, *, use_cache: bool) -> int:
    """Integer micro-USD for one call under the requested cache regime.

    Cascade pricing is expressed by which rate row applies to the call
    (``rates_for`` classifies the call's model), so this function only owns
    the cache and batch axes.
    """

    tokens = row.tokens
    input_tokens = max(0, tokens["inputTokens"])
    cache_read = tokens["cacheReadTokens"] if use_cache else 0
    cache_write = tokens["cacheWriteTokens"] if use_cache else 0
    plain_input = max(0, input_tokens - cache_read - cache_write)

    total = _token_part_micro(plain_input, rates.input)
    if use_cache:
        total += _token_part_micro(cache_read, rates.cache_read)
        total += _token_part_micro(cache_write, rates.cache_write)
    else:
        # no cache: reads/writes bill as plain full-price input
        total += _token_part_micro(cache_read + cache_write, rates.input)
    total += _token_part_micro(tokens["outputTokens"], rates.output)

    if row.batch and use_cache:
        total = total * BATCH_DISCOUNT_MICRO // 1_000_000
    return total


def load_rows(path: Path) -> list[UsageRow]:
    path = Path(path)
    if path.is_dir():
        rows = []
        artifacts_dir = path / "artifacts"
        if not artifacts_dir.is_dir():
            raise SystemExit(f"{path}: not a case bundle (no artifacts/ directory)")
        for artifact_path in sorted(artifacts_dir.glob("*.cbor")):
            artifact = decode(artifact_path.read_bytes())
            if artifact.get("type") == "Telemetry":
                rows.append(row_from_telemetry(artifact))
        return rows
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("calls", payload) if isinstance(payload, dict) else payload
    return [row_from_transcript_record(record) for record in records]


def estimate(rows: list[UsageRow], exact_rates: dict[str, dict[str, int]], baseline_family: str) -> dict:
    optimized = uncached = baseline = 0
    estimated_rows = 0
    batch_rows = 0
    cacheable_input_static = 0
    cacheable_input_total = 0
    per_call = []
    for row in rows:
        rates_current = rates_for(row.model_id, exact_rates)
        rates_baseline = rates_for(baseline_family, exact_rates)
        cost_now = call_cost_micro_usd(row, rates_current, use_cache=True)
        cost_uncached = call_cost_micro_usd(row, rates_current, use_cache=False)
        cost_baseline = call_cost_micro_usd(
            UsageRow(
                tokens={**row.tokens, "cacheReadTokens": 0, "cacheWriteTokens": 0},
                batch=False,
                estimated=row.estimated,
                model_id=baseline_family,
                subject_kind=row.subject_kind,
            ),
            rates_baseline,
            use_cache=False,
        )
        optimized += cost_now
        uncached += cost_uncached
        baseline += cost_baseline
        estimated_rows += 1 if row.estimated else 0
        batch_rows += 1 if row.batch else 0
        if row.input_parts:
            cacheable_input_static += row.input_parts["staticChars"]
            cacheable_input_total += sum(row.input_parts.values())
        per_call.append(
            {
                "subjectKind": row.subject_kind,
                "modelId": row.model_id,
                "estimated": row.estimated,
                "batch": row.batch,
                "optimizedMicroUsd": cost_now,
                "uncachedMicroUsd": cost_uncached,
                "baselineMicroUsd": cost_baseline,
            }
        )

    baseline_ratio = (optimized * 1_000_000 // baseline) if baseline else None
    uncached_ratio = (optimized * 1_000_000 // uncached) if uncached else None
    static_share = (
        cacheable_input_static * 1_000_000 // cacheable_input_total if cacheable_input_total else None
    )
    return {
        "calls": len(rows),
        "estimatedCalls": estimated_rows,
        "batchCalls": batch_rows,
        "cachedStaticShare": static_share,  # micro-share (per-mille style /1e6) of call input that is cache-static
        "optimizedMicroUsd": optimized,
        "uncachedCascadeMicroUsd": uncached,
        "baselineMicroUsd": baseline,
        "optimizedVsBaselineMicroRatio": baseline_ratio,  # optimized * 1e6 / baseline
        "optimizedVsUncachedMicroRatio": uncached_ratio,
        "meetsM4ExitCriterion": bool(
            baseline_ratio is not None and baseline_ratio <= 300_000
        ),
        "perCall": per_call,
    }


def rates_report(exact_rates: dict[str, dict[str, int]], model_ids: list[str]) -> dict:
    report = {}
    for model_id in sorted(set(model_ids)):
        rates = rates_for(model_id, exact_rates)
        report[model_id] = {
            "class": rates.label,
            "inputUsdPerMtokMicro": rates.input,
            "outputUsdPerMtokMicro": rates.output,
            "cacheReadUsdPerMtokMicro": rates.cache_read,
            "cacheWriteUsdPerMtokMicro": rates.cache_write,
        }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M4 token-architecture cost estimator (offline).")
    parser.add_argument("inputs", nargs="+", help="Case bundle directories or provider transcript JSON files")
    parser.add_argument("--provider-config", help="Provider slot YAML used for exact modelFamily pricing overrides")
    parser.add_argument("--baseline-family", default="sonnet", help="Reference family for the no-cache/no-cascade baseline (default: sonnet)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    exact_rates: dict[str, dict[str, int]] = {}
    if args.provider_config:
        from provider_runner import parse_provider_config

        cfg = parse_provider_config(Path(args.provider_config).read_text(encoding="utf-8"))
        exact_rates = cfg.pricing

    rows: list[UsageRow] = []
    for path in args.inputs:
        rows.extend(load_rows(Path(path)))
    if not rows:
        raise SystemExit("no usage-bearing input found (nothing to estimate)")

    estimate_report = estimate(rows, exact_rates, args.baseline_family)
    estimate_report["rates"] = rates_report(exact_rates, [row.model_id for row in rows])
    if not args.json:
        estimate_report.pop("perCall", None)

    if args.json:
        print(json.dumps(estimate_report, indent=2, sort_keys=True))
        return 0

    ratio = estimate_report["optimizedVsBaselineMicroRatio"]
    ratio_text = f"{ratio / 10_000:.2f}%" if ratio is not None else "n/a"
    measured = "measured" if estimate_report["estimatedCalls"] == 0 else (
        f"{estimate_report['estimatedCalls']} of {estimate_report['calls']} calls are USAGE-ESTIMATED"
    )
    print(f"calls={estimate_report['calls']} ({measured}; batch={estimate_report['batchCalls']})")
    static_share = estimate_report["cachedStaticShare"]
    if static_share is not None:
        print(f"cacheable static input share: {static_share / 10_000:.1f}%")
    print(f"optimized:            {estimate_report['optimizedMicroUsd'] / 1_000_000.0:.4f} USD equivalent")
    print(f"uncached (cascade):   {estimate_report['uncachedCascadeMicroUsd'] / 1_000_000.0:.4f} USD equivalent")
    print(f"baseline ({args.baseline_family}-class, no cache/cascade): "
          f"{estimate_report['baselineMicroUsd'] / 1_000_000.0:.4f} USD equivalent")
    print(f"optimized vs baseline: {ratio_text} (M4 exit bound: <=30%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
