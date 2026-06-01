# Feature Roadmap

This roadmap is ordered by practical adoption impact. The goal is to make
Sovereign Conclave a portable, evidence-grounded decision engine rather than a
collection of persona prompts.

Effort scale:

- S: half day
- M: 1-2 days
- L: 3-7 days
- XL: 1-3 weeks

## 0.1.x - Trust the Repository

| Feature | Status | Effort | Notes |
| --- | --- | --- | --- |
| BSD 3-Clause license | Done | S | Public reuse is unblocked. |
| Changelog, progress tracker, security policy | Done | S | Release discipline starts at 0.1.0. |
| Agent validation script | Done | M | `scripts/validate_repo.py` checks frontmatter, model values, footer, stance sections, and no capability claims. |
| Roster alignment validation | Done | S | Validator confirms every `agents/conclave-*.md` appears in config and `roster.md`. |
| 33-seat balance expansion | Done | M | Added two danger lenses, one anti-colonial grievance lens, and two Justice checks with explicit counterweights. |
| Seat expansion rationale | Done | S | `docs/SEAT_EXPANSION_RATIONALE.md` records eligibility, balance, and why these seats are bounded. |
| Installer dry-run tests | Done | S | CI and local checks verify Claude, Codex, and Antigravity targets without touching home directories. |
| CI workflow | Done | M | `.github/workflows/ci.yml` runs shell syntax, repo validation, install dry-run, and runner smoke tests. |

## 0.2.x - Make the Output Irresistible

| Feature | Status | Effort | Notes |
| --- | --- | --- | --- |
| Architecture demo verdict | Done | M | `demos/verdicts/architecture-notifications-platform-split.md` grounds a phased-split decision in supplied artifacts. |
| War-game demo verdict | Done | M | `demos/verdicts/war-game-launch-plan.md` shows blue/red/white cell behavior with a red-cell win. |
| eSiasa civic-stress demo verdict | Done | M | Shows route-backed county dossier reasoning with evidence citations. |
| Pandemic-preparedness demo verdict | Done | M | Demonstrates continuity, public trust, access, and rights checks. |
| Good vs. bad verdict examples | Done | M | `docs/GOOD_VS_BAD_VERDICTS.md` contrasts grounded and ungrounded verdicts on one decision. |
| Evidence Ledger guide and template | Done | M | `docs/EVIDENCE_LEDGER.md` and `demos/evidence-ledger-template.md` define the ledger contract, citation rules, source quality, redactions, and freeze behavior. |
| Evidence-seeded runner scaffolds | Done | M | `bin/conclave` supports repeated `--evidence-file` and `--evidence-note` inputs. |
| Demo ledger validation | Done | S | `scripts/validate_repo.py` checks demo verdict ledger shape and unknown `E#` citations. |
| Machine-readable Evidence Ledger schema | Done | M | `schemas/evidence-ledger.schema.json` defines the model-native JSON form. |
| Ledger import/export runner flags | Done | M | `bin/conclave` supports `--ledger-file` imports, `--validate-ledger` checks, and `--write-ledger` exports. |

## 0.3.x - Make It Portable

| Feature | Status | Effort | Notes |
| --- | --- | --- | --- |
| Local `conclave` runner | Done | M | `bin/conclave` creates deterministic verdict scaffolds from config. |
| Machine-readable roster | Done | L | `configs/conclave-roster.json` lists seats, models, tiers, and paths. |
| Machine-readable profile definitions | Done | L | `configs/conclave-roster.json` lists profiles, seats, polarity pairs, and quorum rules. |
| Config as single source of truth | Done | M | `scripts/generate_roster.py` renders `roster.md` from the config; CI fails on drift. |
| Unit tests + schema enforcement | Done | M | `tests/` cover the validator and runner; CI enforces the JSON schema via `jsonschema`. |
| Provider config schema | Done | M | `scripts/validate_repo.py` validates `configs/provider-model-slots*.yaml` slots, seat coverage, and key-source discipline. |
| Install and uninstall commands | Done | M | `install.sh --uninstall` removes the skill and conclave agents per target. |

## 0.4.x - Make It Collaborative

| Feature | Status | Effort | Notes |
| --- | --- | --- | --- |
| Seat proposal workflow | Planned | S | Require stance, bias, counterweight, and non-overlap proof. |
| GitHub issue and PR templates | Done | S | Bootstrap community intake. |
| Documentation site | Planned | L | Host quickstart, concepts, profiles, and demos. |
| Benchmark decisions | Planned | L | Re-run standard decisions to compare profiles and model routing. |
| Seat collision checks | Done | M | Validator rejects duplicate lenses and advocates without a polarity counterweight. |

## Not Planned by Default

- Autonomous action execution. The Sovereign Conclave advises; the human decides.
- Unbounded all-seat deliberations. Quorums stay small even as the library grows.
- Seats that claim special capability from a name. A persona is a lens, not a
  new skill.
