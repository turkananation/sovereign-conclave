# Local Runner

`bin/conclave` is a deterministic scaffold runner for Sovereign Conclave.

It currently does four things:

1. Reads `configs/conclave-roster.json`.
2. Selects seats from `--profile` or `--members`, or the config `default_profile`
   when neither is given (the assistant protocol in `SKILL.md` instead picks the
   seats most orthogonal to the problem).
3. Optionally seeds the Evidence Ledger from files or explicit notes.
4. Writes a verdict scaffold to `verdicts/` or prints it to stdout.

It does not call model providers, spawn agents, or synthesize a final verdict.
That keeps local execution safe and predictable until provider-backed routing is
implemented.

## Commands

```bash
bin/conclave --list-profiles
bin/conclave --list-seats
bin/conclave --profile architecture --dry-run "Should we split the service?"
bin/conclave --profile risk --stdout "Can this release go out?"
bin/conclave --members feynman,lee-kuan-yew,aurelius "Is the caching design sound?"
bin/conclave --profile risk --evidence-file README.md --evidence-note "Rollback plan is pending owner approval." --stdout "Can this release go out?"
bin/conclave --profile pandemic-preparedness --ledger-file demos/evidence-ledgers/pandemic-preparedness-county-response.json --stdout "Approve the county outbreak-response plan?"
bin/conclave --validate-ledger demos/evidence-ledgers/pandemic-preparedness-county-response.json
bin/conclave --profile risk --evidence-file README.md --write-ledger ledgers/release-risk.json --stdout "Can this release go out?"
```

## Evidence Inputs

Use `--evidence-file` to freeze a local file path and short SHA-256 digest into
the ledger. The runner does not infer claims from the file. The assistant must
quote or cite exact relevant lines before using details from it.

Use `--evidence-note` for an explicit user-supplied note. This proves only that
the note was supplied. It does not transform the underlying assertion into an
independently verified fact.

Both flags may be repeated:

```bash
bin/conclave \
  --profile emergency-powers \
  --evidence-file docs/EVIDENCE_LEDGER.md \
  --evidence-file directives.md \
  --evidence-note "Agency counsel has not approved the emergency order." \
  --stdout "Can the emergency order stay active for another 30 days?"
```

Use `--ledger-file` to import a machine-readable Evidence Ledger JSON file. The
file is validated before the verdict scaffold is rendered. Use
`--validate-ledger` when you only want to validate a ledger file.

Use `--write-ledger` to export the assembled JSON ledger. It works with
`--evidence-file`, `--evidence-note`, and `--ledger-file`. Importing one ledger
keeps its `E#` IDs and appends new evidence after them; importing two or more
ledgers renumbers the merged set into one contiguous sequence so their
overlapping IDs cannot collide. `--write-ledger` is skipped (with a warning to
stderr) under `--dry-run`.

Private JSON ledgers belong under `ledgers/`, which is git-ignored except for
`ledgers/.gitkeep`. Public examples belong under `demos/evidence-ledgers/`.

For manual preparation, use
[demos/evidence-ledger-template.md](../demos/evidence-ledger-template.md).

## Output

Without `--stdout`, the runner writes:

```text
verdicts/verdict-<UTC-timestamp>.md
```

Generated verdicts are ignored by git because they may contain sensitive user
evidence. Curated public examples belong under `demos/verdicts/`.

## Provider mode (opt-in)

By default the runner calls no model. `--provider-run` turns on real
provider-backed deliberation. It is **off by default**, reads credentials **only**
from the environment (Directive D-5), and **falls back to the deterministic
scaffold** when no provider is reachable.

Choose a provider through the environment:

- `CONCLAVE_PROVIDER_CMD` - a command template that receives the prompt on stdin
  and prints the completion on stdout (`{provider}`, `{model_family}`, `{slot}`,
  and `{seat}` are substituted). The universal, provider-agnostic escape hatch.
- `ANTHROPIC_API_KEY` - a built-in Anthropic Messages adapter
  (`CONCLAVE_ANTHROPIC_MODEL` selects the model; default `claude-sonnet-4-6`).

```bash
# Preview routing without calling anything:
bin/conclave --provider-run --profile risk --dry-run "Can this release go out?"

# Run it (writes a filled verdict plus a sibling transcript):
export CONCLAVE_PROVIDER_CMD="your-cli --model {model_family}"
bin/conclave --provider-run --profile architecture "Split the notifications service?"
```

Seats route to provider/model-family slots from
`configs/provider-model-slots*.yaml` (override with `--provider-config`), spreading
polarity partners across providers to reduce monoculture. Each file run writes
`verdict-<stamp>.transcript.json` next to the verdict with per-seat route, timing,
and output; both stay under git-ignored `verdicts/`. `--provider-timeout` bounds
each call. Provider mode runs blind Round 1, Justice checks, Marshall
verification, and a neutral synthesis - and still only advises; it never
authorizes an action (D-4).

## Next Step

The opt-in provider mode keeps the deterministic selection layer and adds
routing, timeouts, and transcript capture. Remaining work: stronger
post-generation validation that every factual claim still cites the frozen
[Evidence Ledger](EVIDENCE_LEDGER.md), and per-slot model maps for the built-in
adapters.
