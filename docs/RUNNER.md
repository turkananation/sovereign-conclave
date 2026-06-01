# Local Runner

`bin/conclave` is a deterministic scaffold runner for Sovereign Conclave.

It currently does three things:

1. Reads `configs/conclave-roster.json`.
2. Selects seats from `--profile` or `--members`.
3. Writes a verdict scaffold to `verdicts/` or prints it to stdout.

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
```

## Output

Without `--stdout`, the runner writes:

```text
verdicts/verdict-<UTC-timestamp>.md
```

Generated verdicts are ignored by git because they may contain sensitive user
evidence. Curated public examples belong under `demos/verdicts/`.

## Next Step

The future provider-backed runner should keep this deterministic selection layer
and add explicit provider routing, timeouts, transcript capture, and validation
that every factual claim still cites the frozen Evidence Ledger.
