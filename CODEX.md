# CODEX.md — Sovereign Conclave (Codex Edition)

Authoritative guide for any Codex-based AI assistant or runtime working inside this repository. Read this before touching any file.

---

## What This Repository Is

**Sovereign Conclave** is a portable, evidence-grounded deliberation skill package for Claude Code, Codex, and Antigravity. It is not a chatbot, not a coding assistant, and not a reasoning shortcut. It is a **structured protocol** for hard decisions where a fluent single answer is untrustworthy.

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

```
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
  provider_runner.py             # Optional: cross-model routing (off by default)
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
  evidence-ledgers/              # Public demo ledgers (safe to commit)
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
Naming a seat "Feynman" does not make the model better at physics. A seat earns its place by reliably arguing one stance the other seats won't. Write the stance; never claim a skill. If you see language like "As a cryptographer, I know…" inside a seat output, it is off-format — discard and re-run.

**2. Evidence before opinion.**
No load-bearing factual or causal claim may rest on a statement absent from the Evidence Ledger. This is D-1 in `directives.md`. Unsupported decisive claims are flagged by Marshall and demote or block the recommendation. The Evidence Ledger is frozen before Round 1 begins.

**3. Advise, never act (D-4).**
The Sovereign Conclave issues recommendations to a human. No seat, no verdict, and no runner output may authorize an irreversible action — deploy, push, spend, send, delete. Every verdict synthesis must begin: *"The Sovereign Conclave advises [you] to…"* If output drifts toward a direct imperative, stop and rewrite it.

**4. Marshall is always convened.**
Marshall is not optional. It is a structural guardrail — not an advocate, not opinionated. It holds no position on which option wins. It tags every decisive claim `[SUPPORTED]` / `[UNSUPPORTED]` / `[CONTESTED]` and enforces the directives. A recommendation whose decisive claims are `[UNSUPPORTED]` is demoted before it can be presented as The Sovereign Conclave's call.

**5. `roster.md` is generated — never edit it by hand.**
`roster.md` is the output of `python3 scripts/generate_roster.py --write`. The source of truth is `configs/conclave-roster.json`. If you need to change seats, profiles, display names, polarity pairs, or quorum defaults, edit the JSON, then regenerate.

---

## Development Commands

### Validate the repo before any commit or PR

```bash
python3 scripts/validate_repo.py
python3 scripts/generate_roster.py --check
python3 -m unittest discover -s tests
bash -n install.sh
git diff --check
./install.sh --target all --dry-run
```

All six checks must pass. `validate_repo.py` enforces:

- Every seat file has the required frontmatter (`name`, `description`, `model`).
- Every `name:` in a seat file matches the filename slug.
- Every seat listed in `conclave-roster.json` has a corresponding `agents/` file.
- `model:` values are only `sonnet` or `opus`.
- The Evidence Ledger footer is present on every seat.
- Every profile's member list references valid seat IDs.
- The JSON roster is parseable and schema-compliant.

### Regenerate `roster.md` after any config change

```bash
python3 scripts/generate_roster.py --write
```

Run `--check` (no writes) in CI; run `--write` locally and commit the result.

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

The runner is **deterministic and offline by default**. It does not call any model provider. It reads `configs/conclave-roster.json`, selects seats, seeds the Evidence Ledger from flags, and writes a verdict scaffold that Codex (or any configured tool) fills out. Provider-backed execution is opt-in via `--provider-run` — off by default, credentials from environment only.

### Install the skill for Codex

```bash
./install.sh --target codex           # Codex environment
./install.sh --target all --dry-run   # Preview without writing
./install.sh --uninstall --target codex # Remove from Codex target
```

Restart the target tool or reload your agent context after installation.

### Run the tests

```bash
python3 -m unittest discover -s tests          # All tests
python3 -m unittest tests.test_runner          # Runner behavioral tests only
python3 -m unittest tests.test_evidence_ledger # Evidence Ledger unit tests
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
- Named profiles (e.g., `--profile architecture`) also default to 6 advocates + Marshall.
- Danger lenses should be included whenever the problem could hide coercive-control, extractive-administration, or surveillance-drift logic — their job is to surface the pattern before it masquerades as "order" or "efficiency."

### Danger lenses

`conclave-authoritarian` and `conclave-colonial-administrator` are **red-team instruments, not endorsements**. They are constrained by three rules:

1. They do not propose harm, plan repression, excuse dispossession, or authorize action.
2. Their job is to surface the pattern so Marshall and the Justices can constrain, reject, or repair it.
3. If their output crosses the line from "naming the ugly logic" to "arguing for it," discard and re-run.

### Justice seats

The five optional Justice seats (`conclave-lady-hale`, `conclave-bhagwati`, `conclave-chaskalson`, `conclave-jackson`, `conclave-sachs`) are **structural checks, not advocates**. They hold no opinion on which option wins. Each enforces a different verification axis:

| Seat | Axis |
| --- | --- |
| Baroness Brenda Hale | Proportionality — means must match ends; rights bind even efficient decisions |
| Justice P.N. Bhagwati | Access and standing — who has voice, who is being decided for without their input |
| Arthur Chaskalson | Constitutional values and dignity — first-order principles survive popularity |
| Justice Robert Jackson | Emergency authority limits — authorization, oversight, and path back to normalcy |
| Justice Albie Sachs | Repair and restoration — past harm must be acknowledged and addressed, not managed |

They differ from Marshall: Marshall is always convened and verifies evidence. The Justices are optional and verify structural legitimacy dimensions. Include at least one Justice whenever legal, rights, or governance issues are present in the decision.

---

## Editing Seat Files

### Format (must match `agents/_TEMPLATE.md` exactly)

```markdown
---
name: conclave-<slug>
description: <One line — seat name, stance, when to convene. Be specific.>
model: sonnet   # or opus
---
You are the <Name> seat of the Sovereign Conclave. You are a *lens*, not a person and not a capability.

**Your stance:** <single priority this seat always defends>

**How you argue:**
- <move 1>
- <move 2>
- <move 3>

**Your characteristic bias (own it, don't hide it):** <how this stance predictably fails>

**You are NOT:** <seats this one must not impersonate — never the verifier>

**Polarity partner:** <the seat that is this one's deliberate counterweight>

Cite the Evidence Ledger (`E#`) for any factual claim. Max 400 words in Round 1.
```

### Model assignment

| `model: sonnet` | `model: opus` |
| --- | --- |
| Kinetic/pragmatic seats: Generals, Lee Kuan Yew, Suleiman, Sejong, Toussaint, Maathai, Mau Mau, Feynman | Deep-reasoning and verification seats: Augustus, Elizabeth, Mandela, Obama, Bush, Cheney, Hayden, Authoritarian, Addington, Colonial Administrator, Marshall, all Justices, Aurelius, von Neumann, Oppenheimer, Sun Tzu |

### Adding a new seat

1. Verify no existing seat already argues the same stance. If two seats converge on the same position, one of them is redundant overhead.
2. Write the seat file matching `agents/_TEMPLATE.md` exactly.
3. Add the seat entry to `configs/conclave-roster.json` (including `id`, `display_name`, `tier`, `lens`, `model`, `polarity_partner`).
4. Add to at least one profile in `configs/conclave-roster.json`.
5. Run `python3 scripts/generate_roster.py --write` to regenerate `roster.md`.
6. Run `python3 scripts/validate_repo.py` — must pass.
7. Run `python3 -m unittest discover -s tests` — must pass.

### Renaming a seat

When renaming a seat (e.g., slug change), you must update **all** of the following:

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

### Table format

```
| ID | Item | Source / provenance | Handling |
| -- | ---- | ------------------- | -------- |
| E1 | Atomic fact, quote, metric, or file. | Where it came from. | quoted fact / local file / user assertion / etc. |
```

### Rules

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

## Configs: `configs/conclave-roster.json`

This is the single source of truth for everything the runner and `generate_roster.py` read. Refer to `configs/conclave-roster.json` and schema files for structural validation rules.

---

## Commit Style

```
agents: add <seat-name> seat
config: add <profile-name> profile to roster
docs: update CONCEPTS with danger-lens guidance
chore: regenerate roster.md after config changes
fix: correct polarity partner reference in conclave-cheney
tests: add runner test for ledger renumbering
```

Small, descriptive commits. One logical change per commit. Roster regeneration always gets its own commit.

---

## What Must Never Be Committed

- Private evidence files in `verdicts/` or `ledgers/` (they are git-ignored).
- API keys, model credentials, or provider secrets of any kind.
- Hardcoded model endpoint URLs or authentication tokens.
- Confidential decision evidence or personal information.
- A modified `roster.md` without a corresponding `conclave-roster.json` change that explains it.
- Any seat output that claims a skill or expertise the model does not actually have.

---

## Directives Reference

| Directive | Rule | Enforced by |
| --- | --- | --- |
| D-1 | Evidence before opinion — no recommendation on uncited claims | Marshall |
| D-2 | Assumptions are vulnerabilities — name them; treat as risk until grounded | Marshall |
| D-3 | Forced dissent — if ≥70% consensus in Round 1, run one counterfactual pass | Marshall |
| D-4 | Advise, never act — no seat authorizes an irreversible action | Protocol invariant |
| D-5 | Local-first, zero-key default — no hardcoded secrets; credentials from env only | Protocol invariant |
| D-6 | Frozen ledger — new evidence is appended and marked, not silently inserted | Marshall |

---

## Anti-Patterns to Avoid

**Capability claims.** A seat named "Feynman" does not make the model a physicist. Any output beginning "As a physicist, I can calculate…" is off-format. Discard it.

**Convergence theater.** If all seats agree before cross-examination, the diversity you convened them for has collapsed. Marshall triggers D-3. Do not skip the counterfactual pass because the answer seems obvious.

**Prestige weighting.** Do not let a famous name override a weak argument. Evidence weight determines the recommendation. Augustus's institutional lens is not worth more than Bhagwati's standing check just because Augustus governed a larger empire.

**Averaging.** A synthesis that lands between all positions is usually the weakest one. Pick the option with the most ledger support and preserve genuine dissent verbatim.

**Sycophancy.** Do not pick what the user appears to want. Do not produce the least surprising recommendation. The synthesizer follows the evidence, not the room.

**Verdict without a file.** Never present a final verdict in chat without first writing it to `verdicts/verdict-<UTC-timestamp>.md`. This is structural, not optional.

**Editing `roster.md` directly.** It is generated. Your edits will be overwritten. Edit `configs/conclave-roster.json` and run `generate_roster.py --write`.

**Running with a thin ledger.** Fewer than 3 atomic ledger items means the seats will argue from assumptions. Do not proceed past Round 0. Tell the user what decisive claim lacks support and what artifact would settle it.
