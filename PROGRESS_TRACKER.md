# Progress Tracker

Current version: 0.1.0

Last updated: 2026-06-01

## Release State

| Area | Status | Evidence |
| --- | --- | --- |
| Core protocol | Complete for 0.1.0 | `SKILL.md` defines evidence ledger, blind analysis, cross-examination, verification, and verdict synthesis. |
| Directives | Complete for 0.1.0 | `directives.md` defines evidence, assumptions, forced dissent, advice-only, and no-secret defaults. |
| Active seats | Complete for 0.1.0 | `agents/` contains 28 active Conclave seats. |
| Roster profiles | Complete for 0.1.0 | `roster.md` lists active seats, polarity pairs, and profile quorums. |
| Installer | Complete for 0.1.0 | `install.sh` supports Claude Code, Codex, Antigravity, and dry-run mode. |
| Verdict output | Complete for 0.1.0 | `demos/verdict-template.md` and `verdicts/.gitkeep` exist. |
| Cross-model example | Complete for 0.1.0 | `configs/provider-model-slots.example.yaml` documents slot routing and environment-key discipline. |
| Public bootstrap docs | Complete for 0.1.0 | `LICENSE`, `CHANGELOG.md`, `FEATURE_ROADMAP.md`, `SECURITY.md`, and contribution docs exist. |

## 0.1.0 Completed

- Established the Sovereign Conclave protocol and guardrails.
- Built the complete core pantheon and eSiasa-oriented extension seats.
- Added structural Justice seats that enforce distinct verification axes.
- Added multi-target installation for Claude Code, Codex, and Antigravity.
- Added provider/model slot example to reduce single-model monoculture.
- Added BSD 3-Clause licensing and repository bootstrap documents.

## Next Milestones

| Milestone | Target | Status | Notes |
| --- | --- | --- | --- |
| 0.1.1 | Validation scripts | Planned | Validate agent files, roster alignment, and installer dry-run output. |
| 0.1.2 | CI bootstrap | Planned | Run shell syntax, markdown checks, and validation scripts on pull requests. |
| 0.2.0 | Demo verdict pack | Planned | Add high-quality sample verdicts that demonstrate the product. |
| 0.3.0 | Portable runner | Planned | Introduce a local runner or CLI wrapper independent of a single assistant environment. |

## Open Questions

- Should `roster.md` remain the source of truth, or should a machine-readable
  roster generate the human-facing document?
- Should generated verdicts stay local-only by default, with examples stored
  separately under `demos/verdicts/`?
- Should provider routing remain an example-only config until a runner exists?
