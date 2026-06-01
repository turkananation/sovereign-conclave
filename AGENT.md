# AGENT.md - Sovereign Conclave

Authoritative guide for any AI agent working inside this repository. Read this before touching any file.

This file is the generic, agent-facing counterpart to `CLAUDE.md`. If protocol, workflow, roster, or validation rules change, keep both files aligned.

# sovereign-conclave / workflow

- Public prompt examples live under `demos/prompts/` and pair with tracked demo ledgers in `demos/evidence-ledgers/` and tracked demo verdicts in `demos/verdicts/`.
- After changing demos/docs, the effective validation stack is: `python3 scripts/validate_repo.py`, `python3 scripts/generate_roster.py --check`, `python3 -m unittest discover -s tests`, `bash -n install.sh`, `./install.sh --target all --dry-run`, `git diff --check`.

## What This Repository Is

**Sovereign Conclave** is a portable, evidence-grounded deliberation skill package for Claude Code, Codex, Copilot-style agents, and other agent runtimes. It is not a chatbot, not a coding assistant persona, and not a reasoning shortcut. It is a **structured protocol** for hard decisions where a fluent single answer is untrustworthy.

The core idea: convene a small quorum of deliberately opposed personas ("seats"), force every factual claim back to a frozen Evidence Ledger, preserve genuine dissent, and write a decision record that advises a human without authorizing action.

This repository contains:

- The `/conclave` protocol (`SKILL.md`, `directives.md`)
- 33 seat definition files (`agents/conclave-*.md`)
- A machine-readable roster and 24 convening profiles (`configs/conclave-roster.json`)
- A local scaffold runner (`bin/conclave`, `scripts/conclave_runner.py`)
- An Evidence Ledger standard (`docs/EVIDENCE_LEDGER.md`)
- CI and validation scripts (`scripts/validate_repo.py`, `scripts/generate_roster.py`)
- Curated public demo prompts, evidence ledgers, and verdicts (`demos/`)
- A multi-target installer (`install.sh`)

## Repository Map

```text
AGENT.md                         # Generic agent-facing operating manual for this repo
CLAUDE.md                        # Claude-specific operating manual; keep aligned with AGENT.md
SKILL.md                         # /conclave protocol - assistant-facing command definition
directives.md                    # Standing rules D-1 through D-6 - enforced by Marshall
roster.md                        # GENERATED - do not edit by hand; regenerate via generate_roster.py
configs/
  conclave-roster.json           # Source of truth for all seats, profiles, and polarity pairs
  provider-model-slots.example.yaml  # Optional cross-model routing example
agents/
  _TEMPLATE.md                   # Canonical shape for every seat file - read before creating seats
  conclave-*.md                  # One file per seat; 33 total
scripts/
  conclave_runner.py             # Local scaffold runner (no model calls)
  evidence_ledger.py             # Evidence Ledger builder/validator library
  validate_repo.py               # Repo invariant checks - must pass before any PR
  generate_roster.py             # Regenerates roster.md from configs/conclave-roster.json
  provider_runner.py             # Optional cross-model routing (off by default)
bin/
  conclave                       # Executable entry point - delegates to conclave_runner.py
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
verdicts/                        # Private generated verdicts - git-ignored except .gitkeep
ledgers/                         # Private machine-readable ledgers - git-ignored except .gitkeep
```

## Operating Model

An agent working here should behave as a protocol maintainer first and a writer second.

- Preserve the repo's core guarantees before improving presentation.
- Treat `SKILL.md`, `directives.md`, and `configs/conclave-roster.json` as the highest-leverage files.
- Prefer fixing root-cause drift instead of patching generated or derived artifacts by hand.
- Never confuse a seat's named persona with actual model capability.
- Never authorize action on behalf of the human decision-maker.

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

All six checks must pass.

`validate_repo.py` enforces at least these invariants:

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

The runner is deterministic and offline by default. It does not call any model provider unless explicitly asked to do so via provider-backed mode. Provider-backed execution is opt-in, off by default, and takes credentials from environment variables only.

### Install the skill

```bash
./install.sh
./install.sh --target codex
./install.sh --target antigravity
./install.sh --target all --dry-run
./install.sh --uninstall --target all
```

Restart the target tool after installation.

### Run targeted tests

```bash
python3 -m unittest discover -s tests
python3 -m unittest tests.test_runner
python3 -m unittest tests.test_evidence_ledger
python3 -m unittest tests.test_provider_runner
```

## Public Example Workflow

Public examples are part of the product surface, not disposable notes.

- Put reusable public prompts in `demos/prompts/`.
- Put the paired machine-readable Evidence Ledger in `demos/evidence-ledgers/`.
- Put the paired public verdict in `demos/verdicts/`.
- Keep example naming stable across all three locations.
- If the example is historical, say so plainly in the prompt, ledger notes, and verdict prose.
- If you add or change public examples, update `README.md` and `docs/README.md` so the example is discoverable.
- After changing demos or repo-facing docs, run the full validation stack listed above.

Example pairing pattern:

- `demos/prompts/self-war-game-repo-readiness.md`
- `demos/evidence-ledgers/self-war-game-repo-readiness.json`
- `demos/verdicts/self-war-game-repo-readiness.md`

## The Protocol at a Glance

Full detail lives in `SKILL.md`. This is the minimum needed to avoid breaking the protocol.

| Round | What happens |
| --- | --- |
| **Round 0** | Assemble the Evidence Ledger. Freeze it. If fewer than 3 atomic items, stop and ask for missing evidence. |
| **Round 0.5** | Frame the actual decision in one sentence. List options, always including "do nothing." Name what is being optimized. Surface load-bearing assumptions. |
| **Round 1** | Spawn seat subagents in parallel, without seeing each other's output. Each output must stay within 400 words and cite ledger items. |
| **Round 2** | Reveal positions. Cross-examine. Marshall verifies decisive claims simultaneously. If early convergence is too clean, trigger a counterfactual pass before synthesis. |
| **Round 3** | The synthesizer writes the verdict to `verdicts/verdict-<UTC-timestamp>.md` using `demos/verdict-template.md`, then reports the path. Section 7 remains for the human. |

Never skip or reorder rounds. Never present a final verdict in chat before the verdict file exists on disk.

### What makes a valid Round 1 output

The output must:

- Open with a one-sentence recommendation and the core reason
- Cite at least one ledger ID (`E#`)
- Stay within 400 words
- Name any load-bearing assumptions not already in the ledger

Discard and re-run any output that:

- Opens with persona biography instead of a stance
- Hedges without making a recommendation
- Claims a capability rather than a lens
- Contains no ledger citations

### What makes a valid Round 2 challenge

A valid challenge names the specific claim, cites the ledger item that weakens or contradicts it or flags it `[UNSUPPORTED]`, and states what changes if the claim falls. "I disagree with Zhukov's confidence" is not a valid challenge.

### Synthesizer rules

- Do not average. The midpoint between all positions is usually the weakest option.
- Do not weight by prestige. Famous names do not get extra authority.
- Do not optimize for what the user appears to want.
- Confidence must track ledger coverage.
- Every synthesis begins with: *"The Sovereign Conclave advises [you] to..."*

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
| Justice (always) | 1 | Marshall - evidence verification, directive enforcement |
| Justice (optional) | 5 | Structural checks: rights, access, dignity, emergency limits, repair |
| Inner Sanctum | 5 | First principles, restraint, formal modeling, dual-use, positioning |
| **Total** | **33** | |

### Quorum rules

- Default: 6 advocate seats plus Marshall
- `--profile half-conclave`: about 17 seats plus Marshall
- `--profile full-conclave`: all 32 advocate seats plus Marshall
- Named profiles still default to 6 advocates plus Marshall unless the profile itself encodes a broader quorum
- Include danger lenses when the problem may hide coercive-control, extractive, or surveillance-drift logic

### Danger lenses

`conclave-authoritarian` and `conclave-colonial-administrator` are red-team instruments, not endorsements.

They must never:

- Propose harm
- Plan repression
- Excuse dispossession
- Authorize action

Their job is to surface ugly governance logic so Marshall and the Justices can constrain or reject it.

### Justice seats

The five optional Justice seats are structural checks, not advocates.

| Seat | Axis |
| --- | --- |
| Baroness Brenda Hale | Proportionality |
| Justice P.N. Bhagwati | Access and standing |
| Arthur Chaskalson | Constitutional values and dignity |
| Justice Robert Jackson | Emergency authority limits |
| Justice Albie Sachs | Repair and restoration |

Marshall remains distinct: Marshall verifies evidence and directives in every run.

## Editing Rules

### Editing seat files

Match `agents/_TEMPLATE.md` exactly. A valid seat file must declare:

- `name`
- `description`
- `model`
- the seat's stance
- how it argues
- characteristic bias
- what it is not
- polarity partner
- the Evidence Ledger citation/footer discipline

Model assignment must remain one of `sonnet` or `opus`.

### Adding a new seat

1. Verify no existing seat already argues the same stance.
2. Create the seat file under `agents/`.
3. Add the seat to `configs/conclave-roster.json`.
4. Add it to at least one profile.
5. Regenerate `roster.md`.
6. Run validation and tests.

### Renaming a seat

When renaming a seat, update all references:

- `agents/` filename and `name:` frontmatter
- `configs/conclave-roster.json`
- any `Polarity partner:` references in other seat files
- `configs/provider-model-slots.example.yaml`
- demo files under `demos/` that mention the old name
- regenerated `roster.md`

Search for the old slug before finishing.

### Editing demos and docs

- Keep public demos sanitized and safe to commit.
- Keep private run artifacts under `verdicts/` and `ledgers/`.
- Never move private verdicts into `demos/` without intentionally rewriting them as public artifacts.
- When a public example claims to be historical, preserve that context so readers do not confuse it with the repo's current state.
- When changing `README.md`, `docs/README.md`, or `demos/`, run the full validation stack.

## The Evidence Ledger Standard

Full spec: `docs/EVIDENCE_LEDGER.md`.

Minimum requirements:

- Atomic entries only
- Stable `E#` IDs after freeze
- Provenance on every row
- Contiguous numbering
- Explicit handling and sensitivity

Storage locations:

| Location | Use | Git |
| --- | --- | --- |
| `verdicts/verdict-<UTC>.md` | Private verdict with embedded ledger | Ignored except `.gitkeep` |
| `ledgers/*.json` | Private machine-readable ledgers | Ignored except `.gitkeep` |
| `demos/evidence-ledgers/*.json` | Public demo ledgers | Tracked |

Never commit private evidence, credentials, or confidential data.

## Configs: `configs/conclave-roster.json`

This is the single source of truth for:

- seats
- profiles
- polarity pairs
- quorum defaults

Key constraints:

- `min_seats` is 6
- `max_seats` is 33
- `display_name` should use the full proper name
- `polarity_partner` must reference a valid seat ID or be `null`
- Any config change requires `roster.md` regeneration

## Profiles and Polarity Pairs

The repo currently carries 24 profiles and 22 polarity pairs. Use profiles when the domain is known and use the polarity system when you need to construct a custom quorum around a core tension.

Examples of core tensions:

- Zhukov vs Washington: audacity vs endurance
- Cheney vs Addington: emergency executive power vs lawful accountability
- Giap vs Pershing: asymmetric protraction vs organized committed mass
- Toussaint vs Augustus: liberation from below vs institutional consolidation from above
- Feynman vs Oppenheimer: first-principles rebuilding vs capability-and-consequence reckoning

## Commit Style

Use small, descriptive commits:

- `agents: add <seat-name> seat`
- `config: add <profile-name> profile to roster`
- `docs: update public example guidance`
- `chore: regenerate roster.md after config changes`
- `fix: correct provider-backed transcript expectation`
- `tests: add runner test for ledger renumbering`

## What Must Never Be Committed

- Private evidence files in `verdicts/` or `ledgers/`
- API keys, model credentials, or provider secrets
- Hardcoded endpoint URLs with secrets
- Confidential decision evidence or personal information
- A hand-edited `roster.md` without the matching config change
- Seat output that claims expertise the model does not actually have

## Directives Reference

| Directive | Rule | Enforced by |
| --- | --- | --- |
| D-1 | Evidence before opinion | Marshall |
| D-2 | Assumptions are vulnerabilities | Marshall |
| D-3 | Forced dissent on premature convergence | Marshall |
| D-4 | Advise, never act | Protocol invariant |
| D-5 | Local-first, zero-key default | Protocol invariant |
| D-6 | Frozen ledger discipline | Marshall |

## Anti-Patterns to Avoid

Common failure modes in this repository:

- Capability claims inside seat outputs
- Convergence theater without real challenge
- Prestige weighting of famous seats
- Splitting the difference instead of choosing the strongest evidence-backed option
- Sycophancy toward the apparent user preference
- Presenting a verdict before writing the file
- Editing `roster.md` directly
- Proceeding with a thin ledger
- Publishing a public demo without its paired prompt or ledger
- Treating a historical demo verdict as if it described the current repository state

## Quick Orientation for a New Agent

1. Read `SKILL.md` to understand the protocol.
2. Read `directives.md` to understand the standing rules.
3. Read `agents/_TEMPLATE.md` and a few seat files before editing seats.
4. Read `docs/CONCEPTS.md` and `docs/GOOD_VS_BAD_VERDICTS.md` to calibrate quality.
5. Inspect `configs/conclave-roster.json` before touching `roster.md`.
6. Use `scripts/validate_repo.py` and the full validation stack to confirm changes.
7. Keep `AGENT.md` and `CLAUDE.md` aligned when the repo's operating rules change.

## Bottom Line

This repository is valuable only if it remains stricter than the average fluent AI workflow. Protect the protocol, protect the evidence standard, protect the generated/config boundary, and protect the human's final authority over action.
