# OPENCODE.md — Sovereign Conclave (OpenCode Edition)

Authoritative guide for any OpenCode-based AI assistant or runtime working inside this repository. Read this before touching any file.

This file is the OpenCode counterpart to `CLAUDE.md`, `GEMINI.md`, and `CODEX.md`. If protocol, workflow, roster, or validation rules change, keep all files aligned.

---

## What This Repository Is

**Sovereign Conclave** is a portable, evidence-grounded deliberation skill package for Claude Code, Codex, Antigravity, and OpenCode. It is not a chatbot, not a coding assistant, and not a reasoning shortcut. It is a **structured protocol** for hard decisions where a fluent single answer is untrustworthy.

The core idea: convene a small quorum of deliberately opposed personas ("seats"), force every factual claim back to a frozen Evidence Ledger, preserve genuine dissent, and write a decision record that advises a human without authorizing action.

This repository contains:

- The `/conclave` protocol (`SKILL.md`, `directives.md`)
- 33 seat definition files (`agents/conclave-*.md`)
- A machine-readable roster and 24 convening profiles (`configs/conclave-roster.json`)
- A local scaffold runner (`bin/conclave`, `scripts/conclave_runner.py`)
- An Evidence Ledger standard (`docs/EVIDENCE_LEDGER.md`)
- CI and validation scripts (`scripts/validate_repo.py`, `scripts/generate_roster.py`)
- Curated demo evidence ledgers and verdicts (`demos/`)
- A multi-target installer (`install.sh`)

---

## Repository Map

```text
AGENT.md                         # Generic agent-facing operating manual for this repo
CLAUDE.md                        # Claude-specific operating manual; keep aligned with AGENT.md
GEMINI.md                        # Gemini/Antigravity-specific operating manual; keep aligned with AGENT.md
CODEX.md                         # Codex-specific operating manual; keep aligned with AGENT.md
OPENCODE.md                      # OpenCode-specific operating manual; keep aligned with AGENT.md
SKILL.md                         # /conclave protocol — the assistant-facing command definition
directives.md                    # Standing rules D-1 through D-6 — enforced by Marshall
roster.md                        # GENERATED — do not edit by hand; regenerate via generate_roster.py
configs/
  conclave-roster.json           # Source of truth for all seats, profiles, and polarity pairs
  provider-model-slots.example.yaml  # Optional cross-model routing example
agents/
  _TEMPLATE.md                   # Canonical shape for every seat file — read before creating seats
  conclave-*.md                  # One file per seat; 33 total
scripts/
  conclave_runner.py             # Local scaffold runner (no model calls)
  evidence_ledger.py             # Evidence Ledger builder/validator library
  validate_repo.py               # Repo invariant checks — must pass before any PR
  generate_roster.py             # Regenerates roster.md from configs/conclave-roster.json
  provider_runner.py             # Optional cross-model routing (off by default)
bin/
  conclave                       # Executable entry point — delegates to conclave_runner.py
tests/
  test_runner.py                 # Behavioral tests for the local runner
  test_evidence_ledger.py        # Evidence Ledger unit tests
  test_provider_runner.py        # Provider runner tests
schemas/
  evidence-ledger.schema.json    # JSON Schema for evidence ledger files
demos/
  evidence-ledger-template.md    # Evidence Ledger template
  verdict-template.md            # Verdict file template
  prompts/                       # Public prompt examples (safe to commit)
  evidence-ledgers/              # Public machine-readable demo ledgers (safe to commit)
  verdicts/                      # Public demo verdicts (safe to commit)
docs/
  CONCEPTS.md                    # Conceptual guide: seats, lenses, danger lenses, Evidence Ledger
  EVIDENCE_LEDGER.md             # Evidence Ledger standard (full spec)
  EXTEND.md                      # Task file for extending the roster
  GOOD_VS_BAD_VERDICTS.md        # Contrast of grounded vs. fluent-but-ungrounded verdicts
  PROGRESS_TRACKER.md            # Seat completion tracking
  QUICKSTART.md                  # Quick-start guide
  RUNNER.md                      # Local runner reference
  SEAT_EXPANSION_RATIONALE.md    # Rationale for each seat's inclusion
verdicts/                        # Private generated verdicts — git-ignored except .gitkeep
ledgers/                         # Private machine-readable ledgers — git-ignored except .gitkeep
```

---

## The Five Invariants

These apply to every file, every seat, every verdict, and every change.

**1. A seat is a lens, not a capability.**
Naming a seat "Feynman" does not make the model better at physics. A seat earns its place by reliably arguing one stance the other seats will not. Write the stance; never claim a skill. If you see language like "As a cryptographer, I know..." inside a seat output, it is off-format and should be discarded.

**2. Evidence before opinion.**
No load-bearing factual or causal claim may rest on a statement absent from the Evidence Ledger. This is D-1 in `directives.md`. Unsupported decisive claims are flagged by Marshall and demote or block the recommendation. The Evidence Ledger is frozen before Round 1 begins.

**3. Advise, never act (D-4).**
The Sovereign Conclave issues recommendations to a human. No seat, no verdict, and no runner output may authorize an irreversible action such as deploy, push, spend, send, or delete. Every verdict synthesis must begin with: *"The Sovereign Conclave advises [you] to..."*

**4. Marshall is always convened.**
Marshall is a structural guardrail, not an advocate. It holds no opinion on which option wins. It tags decisive claims `[SUPPORTED]`, `[UNSUPPORTED]`, or `[CONTESTED]` and enforces the directives. A recommendation whose decisive claims are `[UNSUPPORTED]` is demoted before it can be presented as the Conclave's call.

**5. `roster.md` is generated.**
`roster.md` is the output of `python3 scripts/generate_roster.py --write`. The source of truth is `configs/conclave-roster.json`. Never hand-edit `roster.md`.

---

## Development Commands

### Validate the repo before any commit or PR

```bash
python3 scripts/validate_repo.py
python3 scripts/generate_roster.py --check
python3 -m unittest discover -s tests
bash -n install.sh
./install.sh --target all --dry-run
git diff --check
```

All six checks must pass. `validate_repo.py` enforces at least these invariants:

- Every seat file has the required frontmatter (`name`, `description`, `model`)
- Every `name:` in a seat file matches the filename slug
- Every seat listed in `conclave-roster.json` has a corresponding `agents/` file
- `model:` values are only `sonnet` or `opus`
- The Evidence Ledger footer is present on every seat
- Every profile's member list references valid seat IDs
- The JSON roster is parseable and schema-compliant
- Demo ledgers and demo verdicts are structurally valid

### Regenerate `roster.md` after any config change

```bash
python3 scripts/generate_roster.py --write
```

Run `--check` in validation paths; run `--write` locally when you intentionally changed `configs/conclave-roster.json`, then commit the generated result.

### Run the local verdict scaffold

```bash
bin/conclave --list-profiles
bin/conclave --list-seats
bin/conclave --profile architecture --dry-run "Should we split the service?"
bin/conclave --profile risk --stdout "Can this release go out?"
bin/conclave --members feynman,lee-kuan-yew,aurelius "Is the caching design sound?"
bin/conclave --profile risk \
  --evidence-file README.md \
  --evidence-note "Rollback plan pending owner approval." \
  --stdout "Can this release go out?"
bin/conclave --profile pandemic-preparedness \
  --ledger-file demos/evidence-ledgers/pandemic-preparedness-county-response.json \
  --stdout "Approve the county outbreak-response plan?"
bin/conclave --validate-ledger demos/evidence-ledgers/pandemic-preparedness-county-response.json
bin/conclave --profile risk \
  --evidence-file README.md \
  --write-ledger ledgers/release-risk.json \
  --stdout "Can this release go out?"
```

The runner is **deterministic and offline by default**. It does not call any model provider. It reads `configs/conclave-roster.json`, selects seats, seeds the Evidence Ledger from flags, and writes a verdict scaffold that OpenCode (or any configured tool) fills out. Provider-backed execution is opt-in via `--provider-run` — off by default, credentials from environment variables only.

### Install the skill for OpenCode

```bash
./install.sh --target opencode       # OpenCode environment
./install.sh --target all --dry-run  # Preview without writing
./install.sh --uninstall --target opencode # Remove from OpenCode target
```

`--target opencode` copies the skill into `~/.config/opencode/skills/conclave/` — the global skill discovery location for OpenCode V2. Use `--opencode-dir PATH` only if your OpenCode configuration lives elsewhere.

Post-install, the skill layout is:

```text
~/.config/opencode/skills/conclave/
├── SKILL.md          # Skill entry point (frontmatter carries name + description)
├── directives.md
├── roster.md
├── agents/           # 33 seat definitions read as supporting files
├── configs/
├── demos/
├── docs/
└── schemas/
```

**How OpenCode discovers and loads the skill (OpenCode V2):**

- Skill discovery reads `~/.config/opencode/skills` (global), project `.opencode/skills`, plus `~/.claude/skills` and `.claude/skills` as compatibility sources. There is no `opencode skill install` CLI command — installation is file-based, which is what the installer does.
- The skill **ID is path-derived**: `~/.config/opencode/skills/conclave/SKILL.md` gives ID `conclave`. The frontmatter `name: sovereign-conclave` is a display label, not the ID.
- OpenCode advertises the skill when relevant (the frontmatter `description` drives discovery); the agent then loads it with the `skill` tool using ID `conclave`, or you can mention `@conclave` in a prompt to load it explicitly.
- Precedence: a project-level `.opencode/skills/conclave/` would override this global install for that project. A `~/.claude/skills/conclave/` (installed by `--target claude`) also satisfies OpenCode's compatibility source, but the dedicated `~/.config/opencode/skills` install has the higher precedence.
- Restart OpenCode (or start a new session) after installing so the skill is registered; changes on disk are picked up on subsequent discovery.

Restart OpenCode (or reload your agent context) after installation.

### Run the tests

```bash
python3 -m unittest discover -s tests          # All tests
python3 -m unittest tests.test_runner          # Runner behavioral tests only
python3 -m unittest tests.test_evidence_ledger # Evidence Ledger unit tests
python3 -m unittest tests.test_provider_runner # Provider runner tests only
```

---

## The Protocol at a Glance

Full detail lives in `SKILL.md`. This is the minimum you need to avoid breaking it.

| Round | What happens |
| --- | --- |
| **Round 0** | Assemble the Evidence Ledger. Freeze it. If fewer than 3 atomic items, stop and ask for missing evidence. |
| **Round 0.5** | Frame the actual decision in one sentence. List options (always include "do nothing"). Name what is being optimized. Surface load-bearing assumptions. |
| **Round 1** | Spawn seat subagents **in parallel, without seeing each other's output** (blind). ≤400 words each. Enforce format before passing forward. |
| **Round 2** | Reveal positions. Cross-examination (each seat attacks at least two others with ledger citations). Marshall verifies all decisive claims simultaneously. If ≥3 seats converged in Round 1 without substantive qualification differences, trigger a counterfactual pass before synthesis. |
| **Round 3** | Synthesizer (the main agent, not any seat) writes the verdict to `verdicts/verdict-<UTC-timestamp>.md` using `demos/verdict-template.md`. Reports the path to the human. Leaves Section 7 (Decision) blank. |

**Never skip or reorder rounds.** Never present a verdict in chat without first writing it to `verdicts/`.

### What makes a valid Round 1 output

The output must:

- Open with a one-sentence recommendation and the core reason.
- Cite at least one ledger ID (`E#`).
- Stay within 400 words.
- Name any load-bearing assumptions not already in the ledger.

Discard and re-run any output that:

- Opens with the seat's biographical backstory.
- Hedges the recommendation without a clear stance.
- Claims a capability ("As a general, I know…").
- Contains no ledger citations.

### What makes a valid Round 2 challenge

A valid challenge names the specific claim, cites the ledger item that weakens or contradicts it (or flags it `[UNSUPPORTED]`), and states what changes if the claim falls. "I disagree with Zhukov's confidence" is not a challenge.

### Synthesizer rules

- **Do not average.** A recommendation that lands between all positions is usually the weakest one.
- **Do not weight by prestige.** Bhagwati's standing check is not outranked by Zhukov's decisiveness.
- **Anti-sycophancy.** Do not pick what the user appears to want. Follow the evidence.
- Confidence is tied to ledger coverage: Low = multiple decisive claims `[UNSUPPORTED]`; Medium = most `[SUPPORTED]`, some `[CONTESTED]`; High = all `[SUPPORTED]`, no plausible alternative reading.
- Every synthesis must begin: *"The Sovereign Conclave advises [you] to…"*

---

## Seat Architecture

### Tiers

| Tier | Count | Role |
| --- | --- | --- |
| General | 6 | Kinetic strategy, command, asymmetric warfare |
| Sovereign | 9 | Governance, legitimacy, institutional design |
| Emergency Executive | 1 | Concentrated command authority under existential threat |
| Intelligence | 1 | Hidden threats, collection, secrecy vs. oversight |
| Danger Lens | 2 | Surface ugly governance logic before it hides |
| Law | 1 | Lawful process, accountability, protected records |
| Civic Ecology | 1 | Grassroots stewardship, land, community legitimacy |
| Liberation | 1 | Self-determination, dispossession, sovereignty from below |
| Justice (always) | 1 | Marshall — evidence verification, directive enforcement |
| Justice (optional) | 5 | Structural checks: rights, access, dignity, emergency limits, repair |
| Inner Sanctum | 5 | First principles, restraint, formal modeling, dual-use, positioning |
| **Total** | **33** | |

### Quorum rules

- **Default:** 6 advocate seats + Marshall (7 total). Apply the seat selection heuristic in `SKILL.md`.
- **`--profile half-conclave`:** ~17 seats + Marshall. For cross-domain decisions needing broad coverage.
- **`--profile full-conclave`:** All 32 advocate seats + Marshall. Reserve for civilizational-scale or genuinely irreversible decisions.
- Named profiles (e.g., `--profile architecture`) also default to 6 advocates + Marshall unless the profile encodes a broader quorum.
- Danger lenses should be included whenever the problem could hide coercive-control, extractive-administration, or surveillance-drift logic — their job is to surface the pattern before it masquerades as "order" or "efficiency."

### Danger lenses

`conclave-authoritarian` and `conclave-colonial-administrator` are **red-team instruments, not endorsements**. Their job is to surface ugly governance logic so Marshall and the Justices can constrain or reject it. They must never propose harm, plan repression, excuse dispossession, or authorize action. If their output crosses the line from "naming the ugly logic" to "arguing for it," discard and re-run.

### Justice seats

The five optional Justice seats (`conclave-lady-hale`, `conclave-bhagwati`, `conclave-chaskalson`, `conclave-jackson`, `conclave-sachs`) are **structural checks, not advocates**. Each enforces a different verification axis: proportionality, access and standing, constitutional dignity, emergency-authority limits, and repair. Marshall remains distinct: Marshall is always convened and verifies evidence.

---

## Editing Seat Files

### Format (must match `agents/_TEMPLATE.md` exactly)

A valid seat file must declare `name`, `description`, `model`, the seat's stance, how it argues, its characteristic bias, what it is NOT, its polarity partner, and the Evidence Ledger citation/footer discipline. `model` must remain one of `sonnet` or `opus`. Copy the shape verbatim from `agents/_TEMPLATE.md`; `validate_repo.py` enforces every required section.

### Adding a new seat

1. Verify no existing seat already argues the same stance. If two seats converge on the same position, one of them is redundant overhead.
2. Write the seat file matching `agents/_TEMPLATE.md` exactly.
3. Add the seat entry to `configs/conclave-roster.json` (including `id`, `display_name`, `tier`, `lens`, `model`, `polarity_partner`).
4. Add to at least one profile in `configs/conclave-roster.json`.
5. Run `python3 scripts/generate_roster.py --write` to regenerate `roster.md`.
6. Run `python3 scripts/validate_repo.py` — must pass.
7. Run `python3 -m unittest discover -s tests` — must pass.

### Renaming a seat

When renaming a seat (e.g., slug change), update **all** of the following:

- The `agents/` file itself (rename the file, update `name:` frontmatter).
- `configs/conclave-roster.json` — `id`, `display_name`, any `polarity_partner` references.
- Every other seat file whose `Polarity partner:` line names this seat.
- `configs/provider-model-slots.example.yaml`.
- Any demo verdicts or evidence ledgers under `demos/` that reference the old name.
- Regenerate `roster.md`.
- Verify with `grep -ri "old-name" .` before committing.

---

## The Evidence Ledger Standard

Full spec: `docs/EVIDENCE_LEDGER.md`. The minimum to know:

- **Atomic.** One row = one clear claim. If a file is large, quote the exact relevant lines rather than citing "the file."
- **Stable.** IDs (`E1`, `E2`, …) are assigned in Round 0 and do not change after Round 1 begins. New evidence appended post-freeze is marked as such and called out in the verdict.
- **Provenance-bearing.** Every row says where the item came from: file path, commit, URL, command output, user-supplied note, etc.
- **Contiguous.** No gaps in the ID sequence. When merging multiple `--ledger-file` inputs, the runner renumbers to a single contiguous sequence without duplicates.

### Storage

| Location | Use | Git |
| --- | --- | --- |
| `verdicts/verdict-<UTC>.md` | Private verdict with embedded ledger | Ignored (`.gitkeep` tracked) |
| `ledgers/*.json` | Private machine-readable ledgers | Ignored (`.gitkeep` tracked) |
| `demos/evidence-ledgers/*.json` | Public demo ledgers | Tracked |

Never commit private evidence, confidential data, or API keys.

---

## Cross-Model Diversity in OpenCode (optional)

A conclave of one base model shares one blind-spot set. OpenCode supports many providers under `provider` / `model` configuration in `opencode.json` and via the model switcher. When running with `--models <config>` (see `configs/provider-model-slots.example.yaml`), spread polarity partners across providers where possible so disagreement is real, not stylistic.

**Secrets come from the environment, never from files in this repo or the installed skill (D-5).** Never write provider keys into `opencode.json` or any committed file.

---

## Commit Style

```
agents: add <seat-name> seat
config: add <profile-name> profile to roster
docs: update public example guidance
chore: regenerate roster.md after config changes
fix: correct installer dry-run for opencode target
tests: add runner test for ledger renumbering
```

Small, descriptive commits. One logical change per commit. Roster regeneration always gets its own commit.

---

## What Must Never Be Committed

- Private evidence files in `verdicts/` or `ledgers/` (they are git-ignored).
- API keys, model credentials, or provider secrets of any kind.
- Hardcoded model endpoint URLs or authentication tokens.
- Confidential decision evidence or personal information.
- A modified `roster.md` without a corresponding `configs/conclave-roster.json` change that explains it.
- Any seat output that claims a skill or expertise the model does not actually have.

---

## Directives Reference

| Directive | Rule | Enforced by |
| --- | --- | --- |
| D-1 | Evidence before opinion — no recommendation on uncited claims | Marshall |
| D-2 | Assumptions are vulnerabilities — name them; treat as risk until grounded | Marshall |
| D-3 | Forced dissent on premature convergence — run a counterfactual pass | Marshall |
| D-4 | Advise, never act — no seat authorizes an irreversible action | Protocol invariant |
| D-5 | Local-first, zero-key default — no hardcoded secrets; credentials from env only | Protocol invariant |
| D-6 | Frozen ledger — new evidence is appended and marked, not silently inserted | Marshall |

---

## Anti-Patterns to Avoid

**Capability claims.** A seat named "Feynman" does not make the model a physicist. Any output beginning "As a physicist, I can calculate…" is off-format. Discard it.

**Convergence theater.** If all seats agree before cross-examination, the diversity you convened them for has collapsed. Trigger the D-3 counterfactual pass; do not skip it because the answer seems obvious.

**Prestige weighting.** Do not let a famous name override a weak argument. Evidence weight determines the recommendation.

**Averaging.** A synthesis that lands between all positions is usually the weakest one. Pick the option with the most ledger support and preserve genuine dissent verbatim.

**Sycophancy.** Do not pick what the user appears to want. The synthesizer follows the evidence, not the room.

**Verdict without a file.** Never present a final verdict in chat without first writing it to `verdicts/verdict-<UTC-timestamp>.md`. This is structural, not optional.

**Editing `roster.md` directly.** It is generated. Your edits will be overwritten. Edit `configs/conclave-roster.json` and run `generate_roster.py --write`.

**Running with a thin ledger.** Fewer than 3 atomic ledger items means the seats will argue from assumptions. Do not proceed past Round 0.

---

## Quick Orientation for a New OpenCode Session

1. Read `SKILL.md` to understand the protocol.
2. Read `directives.md` to understand the standing rules.
3. Read `agents/_TEMPLATE.md` and a few seat files before editing seats.
4. Read `docs/CONCEPTS.md` and `docs/GOOD_VS_BAD_VERDICTS.md` to calibrate quality.
5. Inspect `configs/conclave-roster.json` before touching `roster.md`.
6. Use `scripts/validate_repo.py` and the full validation stack to confirm changes.
7. Keep `AGENT.md`, `CLAUDE.md`, `GEMINI.md`, `CODEX.md`, and `OPENCODE.md` aligned when the repo's operating rules change.

---

## Bottom Line

This repository is valuable only if it remains stricter than the average fluent AI workflow. Protect the protocol, protect the evidence standard, protect the generated/config boundary, and protect the human's final authority over action.
