# Progress Tracker

Current version: 0.2.0

Last updated: 2026-10-22

## Release State

| Area | Status | Evidence |
| --- | --- | --- |
| Core protocol | Complete for 0.2.0 | `SKILL.md` defines evidence ledger, blind analysis, cross-examination, verification, and verdict synthesis. |
| Directives | Complete for 0.2.0 | `directives.md` defines evidence, assumptions, forced dissent, advice-only, and no-secret defaults. |
| Active seats | Complete for 0.2.0 | `agents/` contains 33 active Conclave seats, including the balanced expansion. |
| Roster profiles | Complete for 0.2.0 | `roster.md` lists 24 profiles and 22 polarity pairs, generated from the config. |
| Installer | Complete for 0.2.0 | `install.sh` supports Claude Code, Codex, Antigravity, OpenCode, and dry-run mode. |
| Verdict output | Complete for 0.2.0 | `demos/verdict-template.md`, `verdicts/`, and machine exports under `demos/esiasa/exports/`. |
| Cross-model example | Complete for 0.2.0 | `configs/provider-model-slots.example.yaml` documents slot routing and environment-key discipline. |
| Public bootstrap docs | Complete for 0.2.0 | `LICENSE`, `CHANGELOG.md`, `docs/FEATURE_ROADMAP.md`, `SECURITY.md`, and contribution docs exist. |
| Machine-readable roster | Complete for 0.2.0 | `configs/conclave-roster.json` contains seats, profiles, polarity pairs, and quorum rules. |
| Validation and CI | Complete for 0.2.0 | `scripts/validate_repo.py`, unit suite, and `.github/workflows/ci.yml`. |
| Canonical core + bundles | Complete for 0.2.0 | `conclave_core/` canonical DAG-CBOR codecs (CIDs, JCS, merkle) and `scripts/artifact_emitter.py` emit verifier-clean v0.2 case bundles. |
| Signing and transparency | Complete for 0.2.0 | `conclave_core/mldsa.py` (ML-DSA-65, FIPS 204, deterministic keys), certificate chain, identity-signed `SignedTreeHead`s, RFC 6962 inclusion/consistency proofs, and the offline verifier `python3 -m conclave_core.verifier`. |
| Skill retrofit | Complete for 0.2.0 | `SKILL.md` phase wiring to the machine ledger, runner flags for bundle emission, and schema-enforced ledgers. |
| Token architecture | Complete for 0.2.0 | Cached prompts, cascade routing, distillation, committees, telemetry artifacts, and the cost model in `conclave_core` + `scripts/provider_runner.py`. |
| Appeals | Complete for 0.2.0 | `conclave_core/appeals.py`: T1–T3 triggers, finality windows, Tier A/B/C ladder, signed dissent artifacts, supplement ledgers. |
| Conclave server | Complete for 0.2.0 | `conclave_server/`: durable FSM over the artifact store, SSE `/watch`, `/convene`/`/verdict`/`/petition`/`/screening`, civic-public `/artifact`/`/prove`/`/latestSTH`, kill/resume, soft-cap budget ladder. |
| Release verification | Complete for 0.2.0 | `docs/VERIFYING.md` external-party procedure; `demos/esiasa/` release demo machine-verified (`python3 -m conclave_core.verifier demos/esiasa/bundle`). |
| Verdict exports | Complete for 0.2.0 | `scripts/verdict_export.py`: ADR markdown, JSON-LD for the civic portal, self-contained signed HTML with a verification QR; PDF via the documented optional WeasyPrint extra. |

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

## v0.2.0 Roadmap Milestones (docs/plans/v0.2.0-roadmap.md)

| Milestone | Target | Status | Notes |
| --- | --- | --- | --- |
| M0 — OpenCode first-class support | ~1 week | Done | `install.sh` gains the `opencode` target (install/uninstall/`--target all`, CI dry-runs), `OPENCODE.md` operating manual aligned with the other harness docs, platform lists updated repo-wide, skill frontmatter confirmed. |
| M1 — Canonical core | ~2 weeks | Done | Canonical DAG-CBOR artifact codecs, CID addressing, canonical hashing, merkle trees, the v0.2 schema, and the emit/verify skeleton. |
| M2 — Signing & transparency log | ~2 weeks | Done | ML-DSA-65 adapter over `cryptography>=45`, certificate chain, signed tree heads, RFC 6962 proofs, offline verifier CLI. |
| M3 — Skill retrofit | ~2 weeks | Done | `bin/conclave`/`scripts/conclave_runner.py` emit the v0.2 artifact set for a real local run that the M2 verifier validates from artifacts + pubkeys alone; markdown personae unchanged; the deterministic scaffold still works fully offline. |
| M4 — Token architecture | ~3–4 weeks | Done | Cached prompts, cascade, distillation, committees, telemetry artifacts, cost estimator. |
| M5 — Appeals | ~3 weeks | Done | Appeal triggers/windows/ladder, signed dissents, supplement ledgers, bundle verification gates. |
| M6 — conclave_server | ~4 weeks | Done | Durable orchestrator FSM, sessions/hub, HTTP endpoints, SSE streaming, budget ladder, appeal bridge, materialization. |
| M7 — v0.2.0 cut | ~2 weeks | Done | Verdict export tool, eSiasa e2e release demo, `docs/VERIFYING.md`, tagged release `v0.2.0`. |

## Open Questions

- Resolved: `configs/conclave-roster.json` is the source of truth, and
  `scripts/generate_roster.py` generates `roster.md` (CI fails on drift).
- Resolved: generated verdicts stay local-only by default; curated examples
  live under `demos/verdicts/`, and machine-verified release records live
  under `demos/esiasa/`.
- Resolved: provider routing moved from example-only config to the
  operator-side provider adapters (M4), env-key-only, default-off.
- For v0.3+: Flutter observer/verifier UI, T4 stakeholder petitions wired to
  eSiasa identity, external witness co-signing on the transparency log,
  persona marketplace, calibration-weighted voting, and the Swahili-language
  civic portal surface (see the roadmap's deferred section).
