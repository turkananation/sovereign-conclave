# Changelog

All notable changes to Sovereign Conclave are recorded here.

This project follows semantic versioning once public releases begin. Dates use
ISO format.

## [Unreleased]

### Added

- **M2 — signing, certificate chain, and transparency log.** Verdicts, rounds,
  persona manifests, and log checkpoints are now signed end to end:
  - `conclave_core.mldsa`: ML-DSA-65 (FIPS 204) adapter over the vetted
    OpenSSL-backed `cryptography>=45` package. No hand-rolled crypto: the
    OpenSSL implementation does all of the cryptography. Deterministic
    seed-based keypairs (32-byte FIPS 204 seed → 1952-byte public key,
    3309-byte signatures) keep CI and demos reproducible.
  - New artifact types: `Signature`, `KeyPublication`, `Certificate`,
    `SignedTreeHead` (codecVersion 1; validators include key-fingerprint
    self-consistency and dag-cbor payload binding).
  - Hash-then-sign conventions in `conclave_core.signing`: signatures are
    made over the raw binary CID of the payload artifact; FIPS 204 context
    strings (`conclave/<domain>/v1`) provide domain separation (verdict,
    round attestation, orchestrator certification, persona registry, log STH).
  - `conclave_core.merkle`: RFC 6962 transparency-log primitives — leaf/interior
    hashing, audit paths, consistency proofs — transcribed exactly (generators
    from RFC 6962 §2.1, verifiers from RFC 9162 §2.1.3.2/§2.1.4.2), with the
    RFC's worked seven-leaf example pinned as tests.
  - `conclave_core.verifier`: fully offline case verifier
    (`python3 -m conclave_core.verifier <bundle-dir>`, exit 0/1). Validates
    artifact integrity + DAG, the signature chain (identity verdict
    signature, per-case orchestrator certificate, round attestations,
    persona-registry signatures, key possession proofs), and the RFC 6962
    verification path (tree-head roots, consistency proofs, verdict
    inclusion; logged verdicts must be identity-signed and the case verdict
    must appear among the log leaves).
  - M3 — skill retrofit: `bin/conclave --write-bundle` now emits the v0.2
    case bundle for every local run (scaffold runs emit an opening case;
    provider runs additionally record every seat call as a Turn artifact
    with the exact prompt/output bytes referenced by CID, one committed
    Round, and an orchestrator attestation). Emitted bundles verify
    offline: `python3 -m conclave_core.verifier <bundle>`. Long-lived
    keys live in a keystore directory (`conclave_core.keystore`,
    default `~/.conclave/keys`, mode 0600); provider transcripts now
    record the prompt text alongside responses.
  - Deviation from the roadmap: the M2 backend is OpenSSL via
    `cryptography>=45` instead of the planned `pqcrypto` vendor library —
    all bytes are standard FIPS 204 ML-DSA-65.
- **M4 — token architecture: cached prompts, cascade, distillation, committees,
  telemetry, cost model.** Provider deliberations are restructured per the
  roadmap's five compounding cost axes:
  - Prompt architecture: every call is assembled as byte-exact
    `[static prefix]` (standing protocol + frozen ledger + convened roster,
    identical across the whole run) + `[dynamic middle]` (distilled round
    record, identical within a round) + `[persona suffix]` (per seat). The
    Anthropic adapter sends two cache breakpoints (end of static system block,
    end of dynamic block); both clients expose `complete_parts` and return
    provider-reported usage when available.
  - Structured distillation: after every deliberation round a mechanical-tier
    call distills the round's verbatim positions into a `Summary` artifact
    (positions with `[E#]` citations, open disagreements, distilledFrom bound
    to that round's turn CIDs, distiller model and word count). Subsequent
    rounds, the Justice checks, verification, and synthesis consume only the
    distilled record. Distillation failures degrade honestly: the round falls
    back to verbatim positions with a `noDistillationReason` on the Round
    artifact — fidelity never degrades silently. `Summary.fidelityObjections`
    is a validated field for the documented spot-audit protocol
    (`demos/benchmarks/README.md`).
  - Model cascade: provider configs gain `mechanical_slot` (defaults section)
    for distill/consensus/tally routing and a `pricing:` section of integer
    micro-USD-per-million-token rates per model family.
  - Sparse topology: panels larger than twice the committee size run challenge
    rounds through deterministic committee delegates and cross-committee
    attackers (first seat per committee delegates; `chunk[1]` attacks); silent
    seats keep their Round 0 record and vote on the distilled record. Round
    plans truncate to the requested budget.
  - Consensus gating: a mechanical consensus scorer runs while later rounds
    remain; score ≥ threshold with no active dissent ends deliberation early
    and the skip is recorded.
  - Telemetry: new `Telemetry` artifact type, one per provider call — tokens
    (in/out/cache-read/cache-write), provider-reported vs character-estimated
    flag, batch flag, latency, model family/provider, the char split of the
    cached prompt parts, and subject links (`turn` for seat calls, `summary`
    for distillation, `round` for consensus scoring and the synthesizer).
    `Turn` gains an optional `telemetry` link (unused in emit order to avoid
    content-address cycles).
  - Bundle emission: one Round artifact per transcript round index chained by
    `prev` (rounds contiguous across early exit), per-round
    `DOMAIN_ROUND_ATTESTATION` signatures, per-round Summary artifacts, and a
    rounds supersede manifest. Prompt/output bytes of every seat call remain
    resolvable as `<cid>.raw`.
  - Cost model: `scripts/cost_estimator.py` prices bundles or transcripts
    three ways (optimized / uncached-cascade / single-family
    no-cache-no-cascade baseline) with exact floor-division integer
    micro-USD math, builtin rate classes (haiku/sonnet/opus/local) plus exact
    per-family overrides from the provider config, batch discount, and the
    M4 exit-criterion flag. `demos/benchmarks/` ships the ten live-run seeds,
    a deterministic sample transcript (CI estimator smoke), and the operator
    measurement + fidelity spot-audit procedure. CI verifies a scaffold
    bundle end to end and prices the sample transcript.
  - Runner CLI gains `--rounds`, `--consensus-threshold`, `--committee-size`,
    and `--batch`. The default single-round provider flow adds one mechanical
    distiller call (risk profile: 8 → 9 provider calls).
  - Roadmap deviations (documented): telemetry stores raw token counts
    (cache read/write split) rather than a precomputed cache-hit-ratio
    snapshot — ratios are derived downstream in the estimator; the ≤30%
    exit measurement itself needs provider credits, so the in-repo
    deliverable is the estimator + seeds + procedure (no synthetic "measured"
    numbers); memoization covers hash-triple + registry scanning only (full
    replay-adaptation lands with M5/M6 appeal flows); multi-persona packing
    is deferred (the roadmap marks it "sparingly") and `--batch` marks
    whole-run batch eligibility instead.
- `opencode` install target: `./install.sh --target opencode` installs the
  skill into `~/.config/opencode/skills/conclave/`, the global skill discovery
  location for OpenCode, with matching uninstall support and `--opencode-dir`
  override. OpenCode is now listed across the README and all agent manuals
  (`AGENT.md`, `CLAUDE.md`, `GEMINI.md`, `CODEX.md`, `OPENCODE.md`).
- `OPENCODE.md` — OpenCode-specific operating manual aligned with the other
  agent manuals, including V2 skill discovery, ID, and loading semantics.
- CI now verifies the OpenCode install and uninstall dry runs, and
  `validate_repo.py` requires the `OPENCODE.md` manual to stay present.
- **M5 — appeals: triggers, finality windows, the Tier A/B/C ladder; signed
  dissent artifacts.** Every case verdict is now appealable through a
  mechanical public-review flow with one appeal per trigger class:
  - New artifact types in `conclave_core.artifacts`: `Appeal`,
    `AppealScreening`, `AppealVerdict`, `ArbiterRuling` (validated dag-cbor;
    each links the originating verdict and the case manifest — appeals
    reference the manifest chain, they never supersede it — and every
    lifecycle document enters the transparency log). New signing domains:
    `appeal-petition`, `appeal-verdict`, `arbiter-ruling` (screening's domain
    pre-existed); `Verdict` gains an optional `note`.
  - `conclave_core.appeals` — the appeal engine: decodes a bundle into a
    self-consistent CID store, resolves the protocol's
    `appealDefaultWindowDays` finality window (default 30, T2 exempt), and
    enforces the anti-abuse gates: one appeal per trigger class, T4
    infrastructure/build triggers defer to v0.3 with an explicit message; T1
    requires a supplement `EvidenceLedger` chaining to the frozen ledger, T2
    requires mechanically proven violation checks taken from the public
    verifier (a finding cannot be asserted by word alone); pure T3 share
    math (`weight_share_micro` — filed dissent weight over total voting
    weight, in micro-share) auto-schedules Tier B at ≥ 300000 with no gate;
    grant rules (T2 proven checks, T3 threshold, T1 admitted screening with
    latest-wins semantics); Tier A re-deliberation scope; a Tier B panel
    drawn deterministically disjoint from everything already convened
    (the marshall auto-convenes, so drawn seats never double-convene); and a
    Tier C named human arbiter as the final terminus (`dismiss` included for
    the human). Per D-4 the mechanical layer never decides reversal — Tier B
    suggestions are recorded, humans choose.
  - Disposition suggestions: verifier problems prefixed `signature-chain` or
    `log:` suggest `reverse`; everything else suggests `remand`
    (`mechanical_outcome_suggestion`).
  - Verdict emission completes M3's stub: the final scaffold round resolves
    `verdict.finalRound`, votes carry per-seat weight, activeDissent is
    auto-converted to signed `Dissent` artifacts (grounds, `[E#]` cites,
    cited turns), confidence is extracted, and when the dissent share clears
    the T3 threshold the petition is filed at emit time under the per-case
    orchestrator key. The transparency log generalizes: a signed STH per
    growth step, consistency proofs between steps, base64-encoded audit
    paths (verdict + automatic appeal are logged leaves).
  - `append_artifacts_to_bundle` extends an emitted bundle in place without
    touching the manifest chain: artifact files, one logged leaf per
    lifecycle document (`Verdict`, `Dissent`, `EvidenceLedger`, `Appeal`,
    `AppealScreening`, `AppealVerdict`, `ArbiterRuling`), an STH + signature
    per growth step with RFC 6962 consistency proofs, inclusion proofs for
    the new leaves, and a rewritten `bundle.json`. Post-emit lifecycle
    documents are signed with the identity keystore key; per-case
    orchestrator keys remain ephemeral.
  - Runner CLI gains an appeals group: `--show-appeals`,
    `--file-appeal` (T1 takes `--supplement-ledger`; T2 attaches the
    verifier's findings automatically), `--screen-appeal` (`--appeal`,
    `--decision`, `--screen-reasons`), `--adjudicate-appeal` (`--tier A|B`;
    outside T2 the outcome must be explicit), and `--arbitrate-appeal`
    (requires a named human `--arbiter`). Adjudication reviews a clean
    record, or a record carrying proven T2 violations — those are the
    subject of review. Arbitration rulings are custodially signed in v0.2
    (per-human keys arrive later): the identity key signs on behalf of the
    named arbiter and the signature's note records that custody.
  - Acceptance flows are pinned by tests: tamper → verifier findings → T2
    proven+granted → Tier B reversal with a disjoint panel → Tier C closure;
    supplement ledger → admitted screening → Tier A affirm → Tier C
    closure; heavy dissent at emit → automatic T3 logged and verified.
  - Roadmap deviations (documented): provider appellate re-deliberation
    (re-convening the case on a reversed/remanded verdict) lands with the M6
    server; provider-credit measurement of the exit criteria remains
    operator-side.

## [0.1.0] - 2026-06-01

### Added

- First public installable release of Sovereign Conclave for Claude Code,
  Codex, and Antigravity.
- Interactive README banner with grouped Conclave node map, tier arcs, and
  polarity-pair connections.
- CI workflow for shell syntax, repository validation, installer dry-run, and
  local runner smoke tests.
- `scripts/validate_repo.py` for agent, roster, profile, provider-slot, and doc
  invariant checks.
- `configs/conclave-roster.json` as the machine-readable roster/profile source.
- `bin/conclave` and `scripts/conclave_runner.py` for deterministic local
  verdict scaffold generation.
- Quickstart, concepts, and runner documentation under `docs/`.
- Curated demo verdicts for eSiasa civic-stress and pandemic-preparedness
  profiles.
- Expanded the active library from 28 to the original 33-seat target with
  authoritarian-control, colonial-administration, Mau Mau, Jackson, and Sachs
  seats.
- `docs/SEAT_EXPANSION_RATIONALE.md` documenting the 33-seat eligibility
  standard, counterweights, and danger-lens boundaries.
- `oppression-audit`, `decolonization`, and `emergency-powers` convening
  profiles.
- `docs/EVIDENCE_LEDGER.md` and `demos/evidence-ledger-template.md` for the
  Evidence Ledger contract, citation rules, source quality, redactions, and
  freeze procedure.
- Evidence-seeded runner scaffolds via repeated `--evidence-file` and
  `--evidence-note` flags.
- Demo verdict validation for four-column ledgers and unknown `E#` citations.
- `schemas/evidence-ledger.schema.json` for the model-native Evidence Ledger
  JSON format.
- `ledgers/` as the private git-ignored storage location for machine-readable
  ledgers.
- Public demo JSON ledger under `demos/evidence-ledgers/`.
- `--ledger-file`, `--validate-ledger`, and `--write-ledger` runner flags for
  validating, importing, and exporting machine-readable ledgers.
- `scripts/generate_roster.py` to render `roster.md` from the machine-readable
  config, with a CI drift check so the two cannot diverge.
- `tests/` unit suite for the Evidence Ledger validator and the local runner,
  plus byte-compile and unit-test steps in CI.
- CI enforcement of the published Evidence Ledger JSON schema via `jsonschema`,
  and a schema/validator sync check that prevents field drift.
- Provider slot validation for `configs/provider-model-slots*.yaml` (defined
  slots, seat coverage, environment-only keys, no committed secrets).
- Lightweight seat-collision checks: duplicate lenses and advocates without a
  polarity counterweight now fail validation.
- `install.sh --uninstall` to remove the skill and conclave agents per target.
- Architecture and war-game demo verdicts with machine-readable ledgers, and
  `docs/GOOD_VS_BAD_VERDICTS.md`.
- Configurable `default_profile` in the roster config for the local runner.
- Yi Sun-shin <-> Zhukov polarity pair (22 total).
- Opt-in provider-backed runner mode (`bin/conclave --provider-run`): real blind
  Round 1, Justice checks, Marshall verification, and neutral synthesis routed
  across provider slots, with transcript capture. Off by default, credentials
  from the environment only (D-5), graceful fallback to the deterministic
  scaffold, and advice-only output (D-4).

### Fixed

- Verdict files no longer overwrite a prior run written in the same second, and
  the filename now matches the in-file Run ID.
- Merging two or more `--ledger-file` inputs renumbers the combined evidence into
  one contiguous sequence instead of failing on duplicate `E#` IDs.
- The runner warns and skips when `--write-ledger` is combined with `--dry-run`.
- The verdict scaffold renders Justice and verifier rows as structural checks,
  not option recommendations.
- The validator's argument-move count is scoped to the "How you argue" section.

### Changed

- `roster.md` is now generated from `configs/conclave-roster.json`; edit the
  config and run `scripts/generate_roster.py --write`.
- `SKILL.md` overhauled for model-execution fidelity: replaced vague "orthogonal seats"
  instruction with a 4-step axis-and-polarity-pair heuristic; added an explicit
  orchestration checklist (7 ordered steps) so the main agent cannot skip or reorder
  rounds; prescribed a strict Round 1 output format with capability-claim discard rule;
  defined what makes a valid Round 2 challenge (claim → ledger contradiction → consequence);
  prescribed Marshall's structured table output format; changed the convergence trigger
  from unmeasurable `~70%` to a concrete threshold (3+ seats on the same option without
  qualification differences); added Synthesizer rules block covering anti-averaging,
  no-prestige-weighting, anti-sycophancy, ledger-coverage-based confidence calibration
  (Low/Medium/High definitions), and mandatory D-4 phrasing; added three new guardrails
  (anti-sycophancy, confidence-tied-to-evidence, verdict-file-is-mandatory); added
  an 8-row Failure Modes table covering the most common model drift choke points.
