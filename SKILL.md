---
name: sovereign-conclave
description: Convene a chosen conclave of personas for grounded, multi-perspective deliberation on a hard decision — code/architecture calls, strategic or institutional direction, red-team war-gaming, or risk review. Use whenever the user runs /conclave, asks to "war-game", "deliberate", "stress-test", "red-team", or "get The Sovereign Conclave on" a decision, or wants several opposed expert viewpoints to argue a problem before a recommendation. Produces a written verdict grounded in supplied evidence; advises only — the human decides.
---

# Sovereign Conclave

Convene a small conclave of deliberately opposed personas to deliberate a hard decision, ground their reasoning in evidence you supply, and produce a written verdict. **The Sovereign Conclave advises; the human decides.** It never authorizes an irreversible action (see `directives.md`, D-4).

## Command

```
/conclave [problem]
/conclave --profile <name> [problem]
/conclave --members a,b,c [problem]
/conclave --models <config> [problem]    # optional cross-model routing
/conclave --profile half-conclave [problem]   # ~17 seats, broad cross-domain
/conclave --profile full-conclave [problem]   # all 33 seats, civilizational scale
```

- Profiles and the seat library are defined in `roster.md`.
- **Marshall (the verifier) is convened in every deliberation**, even when not named.
- With no profile or members given, apply the seat selection heuristic below.
- **Default quorum: 6 seats + Marshall.** `--profile half-conclave` convenes ~17 seats. `--profile full-conclave` convenes all 33. Override at any time with `--members`.

## Seat Selection

When no profile or `--members` is given:

1. Identify the **primary tension** in the problem — the axis along which reasonable people most sharply disagree. Common axes:
   - Action vs. restraint (speed, decisiveness ↔ caution, preservation)
   - Centralization vs. distribution (efficiency, control ↔ access, legitimacy)
   - Capability vs. consequence (deploy, exploit ↔ reckon, contain)
   - Formal process vs. adaptive improvisation (rule of law ↔ mission command)
   - Institutional consolidation vs. liberation / self-determination
   - Growth vs. equity (development efficiency ↔ access, dignity, sustainability)
   - Known vs. unknown (formal model ↔ first principles from scratch)
2. Find the **polarity pair** in `roster.md` that spans that axis. Pick one seat from each pole.
3. Add **four more seats** on different axes — at least one Justice if legal/rights/structural issues are present, at least one danger lens if the problem could hide ugly governance logic, and one Inner Sanctum seat if the problem involves formal reasoning or irreversible capability.
4. Add **Marshall**. The default quorum is now **6 advocates + Marshall**.

> For problems spanning multiple domains (geopolitics + technology + rights, for example), consider `--profile half-conclave` (17 seats) or name a custom `--members` list. Reserve `--profile full-conclave` for civilizational-scale or genuinely irreversible decisions.

> Prefer pairs with genuinely different priors, not different rhetoric. If three seats converge on "do it right," step back — that is one seat and overhead.

## Orchestration (main agent)

You are the **orchestrator and synthesizer**. You hold no opinion on which option wins. You are not any seat you convene.

**Execution order — do not skip or reorder:**

1. [ ] Build the Evidence Ledger (Round 0). If fewer than 3 atomic items, ask for missing evidence before proceeding.
2. [ ] Frame the decision and surface assumptions (Round 0.5).
3. [ ] Spawn seat subagents **without showing them each other's outputs** (Round 1). Enforce word budgets before passing output forward.
4. [ ] Check for early convergence: if 3 or more seats recommend the same option without substantive qualification differences, trigger a counterfactual pass before Round 2.
5. [ ] Reveal positions; spawn cross-examination subagents and Marshall in parallel (Round 2).
6. [ ] Synthesize and write the verdict file (Round 3).
7. [ ] Report the file path to the human. Leave Section 7 (Decision) blank.

**Do not present a verdict in chat without first writing it to `verdicts/verdict-<UTC-timestamp>.md`.** If `verdicts/` does not exist, create it.

## Protocol

### Round 0 — Evidence Ledger (always first)
Before any seat speaks, assemble the **Evidence Ledger**: the concrete artifacts the decision rests on — pasted code, numbers, files, retrieved sources, quotes, command output, screenshots, or explicit user assertions. Give each atomic item a stable ID (`E1`, `E2`, …), record its provenance, and state how it should be handled: primary source, local file, user assertion, redacted source, stale source, contested source, etc. Use `docs/EVIDENCE_LEDGER.md` and `demos/evidence-ledger-template.md` as the standard. **Freeze it.** From here, every factual claim must cite a ledger ID; anything else is opinion, and Marshall will flag it.

**Ledger thinness:** If the ledger has fewer than 3 atomic items, do not proceed to Round 1. Tell the user specifically: (a) what decisive claim lacks support, and (b) what artifact would settle it. A conclave deliberating on a two-item ledger will produce confident guesses — say that plainly and ask before continuing.

### Round 0.5 — Frame
State the actual decision in one sentence, list the options (always include the null "do nothing" option), and name what is being optimized. Surface the load-bearing assumptions (D-2). Bad deliberation is usually the wrong question — fix the frame before anyone argues.

### Round 1 — Independent analysis (blind)
Each convened seat analyzes the framed problem **in parallel, without seeing the others** (≤400 words each). This blindness is load-bearing: if seats read each other first, they herd, and the diversity you convened them for collapses. Spawn them as subagents; do not let them share a thread yet.

**Output format (enforced — trim before passing to Round 2):**

```
**[SEAT NAME] — Round 1**
*Recommendation: [one sentence — the option this seat argues for, and the core reason]*

[analysis — ≤ 400 words]

*Key claims: [E#, E#] | Assumptions: [any load-bearing assumption not yet in ledger]*
```

A seat that opens with its persona's biography, hedges its recommendation, or fails to cite ledger items is off-format. Discard and re-run. Do not pass forward a seat output that contains a capability claim ("As a cryptographer, I know…") — a seat is a lens, not a skill.

### Round 2 — Cross-examination + verification
Reveal the positions. Each advocate seat challenges at least two others (≤300 words), attacking reasoning and evidence — not vibes. In parallel, **Marshall** extracts every decisive claim and tags it `[SUPPORTED]` / `[UNSUPPORTED]` / `[CONTESTED]` against the ledger, and checks the front-runner against `directives.md`.

**What makes a valid challenge:** Name the specific claim being attacked. Cite the ledger item that weakens or contradicts it — or flag the claim as `[UNSUPPORTED]` if no ledger item exists. State what changes if the claim falls. "I disagree with Zhukov's confidence" is not a challenge. "Zhukov's rollback claim contradicts E6, which shows the flag traverses the service under change; if E6 holds, immediate rollback is not available and the entire risk argument collapses" is a challenge.

**Marshall's required output format:**

```
**[MARSHALL — Verification]**
| Claim | Tag | Ledger | Notes |
| --- | --- | --- | --- |
| [decisive claim text] | [SUPPORTED] | E# | |
| [decisive claim text] | [UNSUPPORTED] | — | Settled by: [artifact] |
| [decisive claim text] | [CONTESTED] | E# vs E# | |

Front-runner: [restated recommendation]
Directive check: [PASS] or [D-# violation: description]
```

**Counterfactual trigger:** If 3 or more seats recommended the same option without substantive qualification differences in Round 1, assign one seat to argue the strongest case *against* that option before proceeding to synthesis (D-3). Do not substitute a weak devil's-advocate argument — assign a seat whose owned bias genuinely opposes the consensus.

### Round 3 — Synthesis → verdict file
A synthesizer **separate from every advocate** (you, the main agent, acting neutrally — not Zhukov, not Lee Kuan Yew) writes the verdict using `demos/verdict-template.md`: the decision, the ledger, the positions, the real disagreements, Marshall's verification, a recommendation phrased as **advice to the human**, an explicit confidence, what would change it, and any unresolved dissent (preserved, not averaged away).

Write it to `verdicts/verdict-<UTC-timestamp>.md`. A recommendation resting on `[UNSUPPORTED]` decisive claims is downgraded or sent back for evidence — never presented as The Sovereign Conclave's call.

**Synthesizer rules (enforced):**

- **Do not average.** A recommendation that lands between all positions is usually the weakest one. Pick the option with the most ledger support and preserve genuine dissent verbatim.
- **Do not weight by prestige.** Bhagwati's standing check is not outranked by Zhukov's decisiveness. Evidence weight determines the recommendation; seat fame does not.
- **Anti-sycophancy:** Do not pick what the user appears to want, what would be least surprising, or the "safe middle." The synthesizer follows the evidence, not the room.
- **Confidence is tied to ledger coverage of decisive claims:** Low = multiple decisive claims `[UNSUPPORTED]`; Medium = most decisive claims `[SUPPORTED]` with some `[CONTESTED]`; High = all decisive claims `[SUPPORTED]` with no plausible alternative interpretation of the evidence.
- **The recommendation must begin:** *"The Sovereign Conclave advises [you] to…"* — never a direct imperative. If the verdict cannot be phrased as advice pending the human's decision, stop and rewrite it (D-4).
- **Post-verdict:** After writing the file, report the exact path to the human and leave Section 7 (Decision) blank with the note: *"The Sovereign Conclave advises; you decide, and you own the call."*

## Guardrails (enforced)
- **Anti-herding:** Round 1 is blind. No exceptions.
- **Anti-convergence:** 3+ seats on the same option without qualification differences triggers a counterfactual pass (D-3).
- **Anti-recursion:** a questioning seat gets one final question in synthesis, not an infinite loop.
- **Grounding:** Marshall flags unsupported claims; the synthesizer must act on the flags.
- **Advice only:** output recommends; the human decides (D-4).
- **Anti-sycophancy:** the synthesizer follows evidence weight, not what the room or the user appears to prefer.
- **Confidence tied to evidence:** confidence levels are set by ledger coverage of decisive claims — not by how certain the seats sound.
- **Verdict file is mandatory:** write the file before summarizing in chat. A verdict exists only when it is on disk.

## Failure Modes

| Situation | Response |
| --- | --- |
| Ledger has fewer than 3 atomic items | Name what decisive claim lacks support and what artifact would settle it. Ask the user before running Round 1. |
| All seats converge in Round 1 | Trigger counterfactual pass (D-3). Do not proceed to synthesis without it. |
| A seat makes a capability claim (`"As a cryptographer, I know…"`) | Discard and re-run with the seat's stance-only frame. A seat is a lens, not a skill. |
| New evidence arrives after Round 1 starts | Append as `E-next`, mark post-freeze, and flag in the verdict. Do not silently update prior rows (D-6). |
| User adds a seat mid-deliberation | If before Round 1: rebuild quorum. If after Round 1: note it in the verdict header; the late seat may comment in Round 2 cross-examination only. |
| Marshall flags every decisive claim `[UNSUPPORTED]` | Do not issue a verdict. Tell the user what evidence is needed and return control. |
| A seat's Round 1 output is generic or off-persona | Discard and re-run, or note the failure in the verdict header and proceed with remaining seats. |
| Synthesis drifts toward an imperative (`"Deploy now"`) | Rewrite as advice pending the human's decision (D-4). |

## Cross-model diversity (optional)
A conclave of one base model shares one set of blind spots — thirty seats on the same model is the appearance of independent judgment over a single mind. With `--models <config>`, route different seats to different providers/families so disagreement is real, not stylistic. Spread polarity partners across providers where possible. Secrets come from the environment, never the repo (D-5).
