# Changelog

All notable changes to Sovereign Conclave are recorded here.

This project follows semantic versioning once public releases begin. Dates use
ISO format.

## [Unreleased]

### Added

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

## [0.1.0] - 2026-06-01

### Added

- Initial Sovereign Conclave skill protocol with evidence-ledger grounding,
  blind Round 1 deliberation, cross-examination, Marshall verification, and
  verdict-file synthesis.
- Twenty-eight active Conclave seats covering generals, sovereigns, Justices,
  inner-sanctum reasoning seats, and eSiasa-oriented governance, continuity,
  intelligence, law, and ecological-civic lenses.
- Multi-target installer for Claude Code, Codex, and Antigravity.
- Roster profiles for architecture, strategy, risk, institutional, policy,
  liberation, war-game, eSiasa civic-stress, continuity,
  pandemic-preparedness, intelligence oversight, and environmental governance.
- Verdict template and tracked `verdicts/` output directory.
- Example provider/model slot mapping for optional cross-model routing.
- BSD 3-Clause license.
