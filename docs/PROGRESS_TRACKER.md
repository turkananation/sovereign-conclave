# Progress Tracker

Current version: 0.1.0

Last updated: 2026-06-01

## Release State

| Area | Status | Evidence |
| --- | --- | --- |
| Core protocol | Complete for 0.1.0 | `SKILL.md` defines evidence ledger, blind analysis, cross-examination, verification, and verdict synthesis. |
| Directives | Complete for 0.1.0 | `directives.md` defines evidence, assumptions, forced dissent, advice-only, and no-secret defaults. |
| Active seats | Complete after 0.1.0 | `agents/` contains 33 active Conclave seats, including the balanced expansion. |
| Roster profiles | Complete after 0.1.0 | `roster.md` lists 15 profiles and 22 polarity pairs, generated from the config. |
| Installer | Complete for 0.1.0 | `install.sh` supports Claude Code, Codex, Antigravity, and dry-run mode. |
| Verdict output | Complete for 0.1.0 | `demos/verdict-template.md` and `verdicts/.gitkeep` exist. |
| Cross-model example | Complete for 0.1.0 | `configs/provider-model-slots.example.yaml` documents slot routing and environment-key discipline. |
| Public bootstrap docs | Complete for 0.1.0 | `LICENSE`, `CHANGELOG.md`, `docs/FEATURE_ROADMAP.md`, `SECURITY.md`, and contribution docs exist. |
| Machine-readable roster | Complete after 0.1.0 | `configs/conclave-roster.json` contains seats, profiles, polarity pairs, and quorum rules. |
| Validation and CI | Complete after 0.1.0 | `scripts/validate_repo.py` and `.github/workflows/ci.yml` exist. |
| Local runner scaffold | Complete after 0.1.0 | `bin/conclave` creates verdict scaffolds from the machine-readable roster. |
| Demo verdicts | Complete after 0.1.0 | `demos/verdicts/` includes eSiasa civic-stress and pandemic-preparedness examples. |
| Evidence Ledger | Complete after 0.1.0 | `docs/EVIDENCE_LEDGER.md`, `schemas/evidence-ledger.schema.json`, `demos/evidence-ledger-template.md`, runner evidence flags, JSON validation/import/export, and demo ledger validation define and seed frozen ledgers. |
| User docs | Complete after 0.1.0 | `docs/README.md`, `docs/QUICKSTART.md`, `docs/CONCEPTS.md`, `docs/EVIDENCE_LEDGER.md`, and `docs/RUNNER.md` exist. |

## 0.1.0 Completed

- Established the Sovereign Conclave protocol and guardrails.
- Built the complete core pantheon and eSiasa-oriented extension seats.
- Added structural Justice seats that enforce distinct verification axes.
- Added multi-target installation for Claude Code, Codex, and Antigravity.
- Added provider/model slot example to reduce single-model monoculture.
- Added BSD 3-Clause licensing and repository bootstrap documents.

## After 0.1.0 Completed

- Expanded the library from 28 to the original 33-seat target.
- Added bounded danger lenses for authoritarian control and colonial administration.
- Added Mau Mau as an anti-colonial land, dignity, and closed-channel grievance lens.
- Added Jackson and Sachs as Justice checks for emergency powers and repair/transitional legitimacy.
- Added `oppression-audit`, `decolonization`, and `emergency-powers` convening profiles.
- Documented the expansion standard and counterweights in `docs/SEAT_EXPANSION_RATIONALE.md`.
- Built out the Evidence Ledger as a documented contract, reusable template, richer verdict table, runner-seeded input path, schema-backed JSON format, private `ledgers/` storage convention, and import/export runner flow.
- Made `configs/conclave-roster.json` the single source of truth: `scripts/generate_roster.py` renders `roster.md` with a CI drift check.
- Added a `tests/` unit suite, CI schema enforcement via `jsonschema`, provider-slot and seat-collision validation, an `install.sh --uninstall` path, architecture and war-game demo verdicts, and `docs/GOOD_VS_BAD_VERDICTS.md`.
- Hardened the local runner: collision-safe verdict filenames, contiguous multi-ledger merge, type-aware scaffold rows, and a configurable `default_profile`.
- Added an opt-in provider-backed runner mode (`--provider-run`) with env-only keys, default-off, graceful fallback, slot routing, and transcript capture.

## Next Milestones

Milestone labels track planned work, not releases. Completed milestones are
unreleased and accumulate under CHANGELOG `[Unreleased]`; the published version
stays **0.1.0** until a release is cut.

| Milestone | Target | Status | Notes |
| --- | --- | --- | --- |
| 0.1.1 | Validation scripts | Done | Validate agent files, roster alignment, provider slots, docs, and installer dry-run output. |
| 0.1.2 | CI bootstrap | Done | Run shell syntax, validation scripts, installer dry-run, and local runner smoke tests. |
| 0.1.3 | 33-seat balance pass | Done | Finalize original 33-seat target with documented eligibility, counterweights, and danger-lens boundaries. |
| 0.1.4 | Evidence Ledger buildout | Done | Add guide, template, source-quality rules, redaction handling, and runner evidence flags. |
| 0.1.5 | Model-native ledgers | Done | Add JSON schema, public demo JSON ledger, private `ledgers/` storage, validation, and runner import/export. |
| 0.2.0 | Demo verdict pack | Done | eSiasa civic-stress, pandemic-preparedness, architecture, and war-game demos plus a good-vs-bad guide are in. |
| 0.3.0 | Portable runner | Done | Deterministic scaffold plus an opt-in provider-backed mode (env-only keys, default off, transcript capture). |

## Open Questions

- Resolved: `configs/conclave-roster.json` is the source of truth, and
  `scripts/generate_roster.py` generates `roster.md` (CI fails on drift).
- Should generated verdicts stay local-only by default, with examples stored
  separately under `demos/verdicts/`?
- Should provider routing remain an example-only config until a runner exists?
