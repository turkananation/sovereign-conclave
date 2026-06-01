# Changelog

All notable changes to Sovereign Conclave are recorded here.

This project follows semantic versioning once public releases begin. Dates use
ISO format.

## [Unreleased]

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
