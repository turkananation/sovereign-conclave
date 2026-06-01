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

### Planned

- Add richer demo verdicts for architecture and war-game profiles.

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
