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
| Agent validation script | Planned | M | Check frontmatter, model values, footer, stance sections, and no capability claims. |
| Roster alignment validation | Planned | S | Confirm every `agents/conclave-*.md` appears in `roster.md` and vice versa. |
| Installer dry-run tests | Planned | S | Verify Claude, Codex, and Antigravity targets without touching home directories. |
| CI workflow | Planned | M | Run shell syntax, markdown checks, and repo validators on pull requests. |

## 0.2.x - Make the Output Irresistible

| Feature | Status | Effort | Notes |
| --- | --- | --- | --- |
| Architecture demo verdict | Planned | M | Show a realistic technical decision grounded in supplied artifacts. |
| War-game demo verdict | Planned | M | Show blue/red/white cell behavior clearly. |
| eSiasa civic-stress demo verdict | Planned | M | Best showcase for the repo's distinctive governance use case. |
| Pandemic-preparedness demo verdict | Planned | M | Demonstrates continuity, public trust, access, and rights checks. |
| Good vs. bad verdict examples | Planned | M | Teach why evidence grounding beats fluent guessing. |
| Evidence-ledger examples | Planned | M | Help users provide useful inputs before the Conclave speaks. |

## 0.3.x - Make It Portable

| Feature | Status | Effort | Notes |
| --- | --- | --- | --- |
| Local `conclave` runner | Planned | L | Run the protocol outside a specific assistant UI. |
| Machine-readable roster | Planned | L | Add `roster.yaml` or equivalent and generate docs from it. |
| Machine-readable profile definitions | Planned | L | Make profile selection testable and tool-friendly. |
| Provider config schema | Planned | M | Validate `configs/provider-model-slots*.yaml`. |
| Install and uninstall commands | Planned | M | Make adoption and rollback predictable. |

## 0.4.x - Make It Collaborative

| Feature | Status | Effort | Notes |
| --- | --- | --- | --- |
| Seat proposal workflow | Planned | S | Require stance, bias, counterweight, and non-overlap proof. |
| GitHub issue and PR templates | Done | S | Bootstrap community intake. |
| Documentation site | Planned | L | Host quickstart, concepts, profiles, and demos. |
| Benchmark decisions | Planned | L | Re-run standard decisions to compare profiles and model routing. |
| Seat collision checks | Planned | L | Detect overlapping lenses before roster quality decays. |

## Not Planned by Default

- Autonomous action execution. The Conclave advises; the human decides.
- Unbounded all-seat deliberations. Quorums stay small even as the library grows.
- Seats that claim special capability from a name. A persona is a lens, not a
  new skill.
