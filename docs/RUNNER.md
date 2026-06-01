# Local Runner

`bin/conclave` is a deterministic scaffold runner for Sovereign Conclave.

It currently does four things:

1. Reads `configs/conclave-roster.json`.
2. Selects seats from `--profile` or `--members`.
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

Use `--write-ledger` to export the assembled JSON ledger. This works with
`--evidence-file`, `--evidence-note`, and `--ledger-file`; if a ledger file is
loaded and new evidence is supplied, the runner appends new `E#` IDs after the
existing IDs.

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

## Next Step

The future provider-backed runner should keep this deterministic selection layer
and add explicit provider routing, timeouts, transcript capture, and validation
that every factual claim still cites the frozen
[Evidence Ledger](EVIDENCE_LEDGER.md).
