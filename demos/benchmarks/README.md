# M4 benchmark: token-architecture cost measurement

The M4 exit criterion (roadmap) is a **measured** result: mounted on real
provider runs, the optimized deliberation (prompt cache + model cascade +
optional batch) must land at **≤30% of the cascaded baseline** — the same
deliberation priced at v0.1-style economics (single sonnet-class family, no
cache discounts). Everything needed to *compute* that number from a run is in
the repository; actually running the ten seeds needs provider credits, so the
in-repo deliverables are the seeds, the estimator, and this procedure.

## What ships in-repo

| Artifact | Role |
| --- | --- |
| `benchmarks.json` | Ten live-deliberation seeds (profile + ledger + question). |
| `transcript-sample.json` | Deterministic mini transcript; CI smoke input for the estimator. |
| `scripts/cost_estimator.py` | Prices bundles/transcripts three ways with exact integer micro-USD math. |
| Telemetry artifacts | Every bundle from a `--provider-run` carries per-call `Telemetry` artifacts (tokens, cache read/write split, latency, batch flag, estimated flag). |

## Operator procedure (per seed)

1. Configure routing: copy `configs/provider-model-slots.example.yaml` to
   `configs/provider-model-slots.yaml`, point `model_family`s at real models, and
   set the `pricing:` section to YOUR contract rates (integer micro-USD per
   million tokens). Builtin fallback rates are documented approximations of
   public list prices — do not rely on them for a filing.
2. Export provider access per Directive D-5 (environment only, never files and
   never committed): `CONCLAVE_PROVIDER_CMD` or `ANTHROPIC_API_KEY`, plus the
   standard conclave keystore seeds if you want a signed bundle.
3. Run the seed. Recommended flags for the measured configuration:

   ```sh
   bin/conclave --provider-run --profile <profile> \
       --ledger-file <ledger.json> --rounds 2 --committee-size 7 \
       --out-dir /tmp/bench/seed-<n> \
       "<question>"
   ```

   Then the estimator over the emitted bundle (and/or the runner transcript):

   ```sh
   python3 scripts/cost_estimator.py /tmp/bench/seed-<n>/bundle-* \
       --provider-config configs/provider-model-slots.yaml \
       --baseline-family sonnet --json > /tmp/bench/seed-<n>/cost.json
   ```

4. Record per seed: `optimizedMicroUsd`, `baselineMicroUsd`,
   `optimizedVsBaselineMicroRatio`, `meetsM4ExitCriterion`, the estimated-call
   count, and the `cachedStaticShare`. A seed counts toward the exit criterion
   only when `estimatedCalls == 0` (all calls provider-report usage) and
   fidelity audit passes (below).

## Regimes and definitions

- **optimized** — billed cost: cascade tiers, cache reads ~0.1x, cache writes
  ~1.25x, flat 0.5x on batch-marked calls. `inputTokens` is treated as
  inclusive of cache read/write per provider reporting semantics.
- **uncached (cascade)** — same call plan and families, all cache discounts off.
- **baseline** — no cache AND no cascade: every call repriced at one family
  (`--baseline-family`, default sonnet-class) at list input price. This is the
  v0.1-style counterfactual.
- Character-estimated calls (`Telemetry.estimated = true`) are included in all
  regimes at ~4 chars/token, but a seed only *counts* when none are estimated.

## Fidelity spot-audit protocol

Cost without fidelity is cheating; the audit closes the loop per roadmap M4:

1. For one audited seed per batch, run an independent opus-class pass comparing
   each round's distilled `Summary` artifact against the round's raw turns (the
   bundle's `*.raw` prompt/output payloads).
2. Any dropped minority-of-one position, altered stance, invented citation, or
   averaged-away dissent is a **fidelity objection**.
3. File objections as `fidelityObjections` on the Summary artifact (the field
   is validated, list of strings) and re-run the seed with the objections in
   the distiller context (one-shot re-distill). A seed passes only after a
   re-audit with zero objections.
4. Record the objection count next to `cost.json` (e.g.
   `fidelityObjections: 0` in the seed's notes). `meetsM4ExitCriterion` alone
   is not sufficient.

## Multi-round / committee cost knobs

- `--rounds N` (default 1): challenge rounds consume the **distilled record**,
  not raw transcripts — the 70–90% input reduction comes mostly from this.
- `--committee-size 7` (default 7, `0` disables): sparse topology engages only
  for large panels (> 2× committee size); committee/cross rounds speak through
  deterministic delegates (first seat per committee; `chunk[1]` as attacker).
- `--consensus-threshold 85`: early exit skips remaining challenge rounds once
  the mechanical scorer reports consensus at/above threshold with no active
  dissent.
- `--batch`: marks calls batch (telemetry flag + 50% cost-model discount).

## Known deviations from the roadmap (documented honestly)

- The ≤30% number is *operator-measured*; this repo provides the estimator,
  seeds, and procedure (no provider credits are available in CI).
- Memoization is a hash-triple + registry scan (full replay-adaptation lands
  with M5/M6's appeal flows).
- Multi-persona packing (batching distinct seats into one request) is deferred;
  `--batch` currently marks whole-run batch eligibility per invocation.
