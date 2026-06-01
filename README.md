# Sovereign Conclave

Your own Claude Code skill: a chosen council of personas that argue a hard decision from deliberately opposed stances, ground their claims in evidence you supply, and hand you a written verdict. It advises; you decide.

**This is an independent project — not a fork.** The convening pattern (multi-perspective deliberation) is a common one; the design here is yours — your roster, your directives, your verdict format. There is a conceptual nod to the public-domain "council" pattern that's been circulating, but no code is shared with it and nothing depends on anyone merging anything.

## What's in the box

- `SKILL.md` — the `/conclave` command and the deliberation protocol.
- `agents/conclave-*.md` — the active seats: four advocates + Marshall, the verifier.
- `agents/_TEMPLATE.md` — how to add a seat from your bench.
- `roster.md` — the full library, the bench (your pantheon), and the convening profiles.
- `directives.md` — the standing rules Marshall enforces (including "advise, never act").
- `demos/verdict-template.md` — the decision-record format the council writes to.
- `install.sh` — drops the skill + subagents into `~/.claude`.

## Install

```bash
./install.sh            # or:  ./install.sh --dry-run   to preview
```

Restart Claude Code; `/conclave` becomes available.

## Use

```
/conclave Should we move the notifications service off Cloud Run?
/conclave --profile architecture Monorepo or polyrepo for the new modules?
/conclave --profile war-game Pressure-test our launch plan for next quarter.
/conclave --members feynman,lee-kuan-yew,marshall Is the caching design sound?
```

Paste or attach the real artifacts — code, numbers, the doc. They become the **Evidence Ledger**, and Marshall flags any claim that isn't backed by it.

## The two rules that make this more than theater

1. **Grounded, or flagged.** Every load-bearing claim cites the Evidence Ledger; Marshall marks the rest `[UNSUPPORTED]`. Deliberation organizes reasoning — it does not manufacture truth. The grounding is what keeps a well-formatted guess from passing as a verdict.
2. **Advise, never act.** The Conclave produces a recommendation *for you*. It never authorizes an irreversible action. You decide; you own it.

## Growing the roster

Convene small — three to eight seats plus Marshall. The library in `roster.md` can be as large as you like; the meeting stays small. Add a seat only when it argues a stance no current seat covers: copy `_TEMPLATE.md`, write the lens, done. A seat that agrees with one you already have is just cost — and a persona is a *lens*, never a claim that the model gained a skill it lacked.

## License

Yours to choose. MIT or CC0 keep it friction-free if you ever open it up.
