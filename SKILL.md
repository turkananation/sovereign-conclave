---
name: sovereign-conclave
description: Convene a chosen conclave of personas for grounded, multi-perspective deliberation on a hard decision — code/architecture calls, strategic or institutional direction, red-team war-gaming, or risk review. Use whenever the user runs /conclave, asks to "war-game", "deliberate", "stress-test", "red-team", or "get the conclave on" a decision, or wants several opposed expert viewpoints to argue a problem before a recommendation. Produces a written verdict grounded in supplied evidence; advises only — the human decides.
---

# Sovereign Conclave

Convene a small conclave of deliberately opposed personas to deliberate a hard decision, ground their reasoning in evidence you supply, and produce a written verdict. **The Conclave advises; the human decides.** It never authorizes an irreversible action (see `directives.md`, D-4).

## Command

```
/conclave [problem]
/conclave --profile <name> [problem]
/conclave --members a,b,c [problem]
/conclave --models <config> [problem]    # optional cross-model routing
```

- Profiles and the seat library are defined in `roster.md`.
- **Marshall (the verifier) is convened in every deliberation**, even when not named.
- With no profile or members given, pick a 3-seat quorum from `roster.md` whose stances are most orthogonal to the problem, plus Marshall.

## Protocol

### Round 0 — Evidence Ledger (always first)
Before any seat speaks, assemble the **Evidence Ledger**: the concrete artifacts the decision rests on — pasted code, numbers, files, retrieved sources, quotes, command output, screenshots, or explicit user assertions. Give each atomic item a stable ID (`E1`, `E2`, …), record its provenance, and state how it should be handled: primary source, local file, user assertion, redacted source, stale source, contested source, etc. Use `docs/EVIDENCE_LEDGER.md` and `demos/evidence-ledger-template.md` as the standard. **Freeze it.** From here, every factual claim must cite a ledger ID; anything else is opinion, and Marshall will flag it. If the ledger is thin, say so plainly — a conclave deliberating without evidence produces confident guesses, not judgment.

### Round 0.5 — Frame
State the actual decision in one sentence, list the options (always include the null "do nothing" option), and name what is being optimized. Surface the load-bearing assumptions (D-2). Bad deliberation is usually the wrong question — fix the frame before anyone argues.

### Round 1 — Independent analysis (blind)
Each convened seat analyzes the framed problem **in parallel, without seeing the others** (≤400 words each). This blindness is load-bearing: if seats read each other first, they herd, and the diversity you convened them for collapses. Spawn them as subagents; do not let them share a thread yet.

### Round 2 — Cross-examination + verification
Reveal the positions. Each advocate seat challenges at least two others (≤300 words), attacking reasoning and evidence — not vibes. In parallel, **Marshall** extracts every decisive claim and tags it `[SUPPORTED]` / `[UNSUPPORTED]` / `[CONTESTED]` against the ledger, and checks the front-runner against `directives.md`.

If Round 1 showed early consensus (D-3), run one **counterfactual pass**: assign a seat to argue the strongest case *against* the emerging answer before proceeding.

### Round 3 — Synthesis → verdict file
A synthesizer **separate from every advocate** (you, the main agent, acting neutrally — not Zhukov, not Lee Kuan Yew) writes the verdict using `demos/verdict-template.md`: the decision, the ledger, the positions, the real disagreements, Marshall's verification, a recommendation phrased as **advice to the human**, an explicit confidence, what would change it, and any unresolved dissent (preserved, not averaged away).

Write it to `verdicts/verdict-<UTC-timestamp>.md`. A recommendation resting on `[UNSUPPORTED]` decisive claims is downgraded or sent back for evidence — never presented as the conclave's call.

## Guardrails (enforced)
- **Anti-herding:** Round 1 is blind. No exceptions.
- **Anti-convergence:** early agreement triggers a counterfactual pass (D-3).
- **Anti-recursion:** a questioning seat gets one final question in synthesis, not an infinite loop.
- **Grounding:** Marshall flags unsupported claims; the synthesizer must act on the flags.
- **Advice only:** output recommends; the human decides (D-4).

## Cross-model diversity (optional)
A conclave of one base model shares one set of blind spots — thirty seats on the same model is the appearance of independent judgment over a single mind. With `--models <config>`, route different seats to different providers/families so disagreement is real, not stylistic. Spread polarity partners across providers where possible. Secrets come from the environment, never the repo (D-5).
