# Prompt - Self War-Game: Repo Release Readiness

This public prompt produced the historical self-war-game example in:

- `demos/verdicts/self-war-game-repo-readiness.md`
- `demos/evidence-ledgers/self-war-game-repo-readiness.json`

Use it when you want Sovereign Conclave to inspect its own repository state and decide whether the project is ready for broad external release, should be held for hardening, or should be limited to a caveated beta/internal posture.

## Prompt

```text
/conclave --profile full-conclave War-game this whole repository as a public release candidate. Use the repository itself as the primary evidence source. Build the Evidence Ledger from SKILL.md, directives.md, README.md, SECURITY.md, docs/RUNNER.md, scripts/validate_repo.py, scripts/provider_runner.py, configs/conclave-roster.json, and the current validation commands (`python3 scripts/validate_repo.py`, `python3 scripts/generate_roster.py --check`, `python3 -m unittest discover -s tests`, `bash -n install.sh`, `./install.sh --target all --dry-run`, and `git diff --check`). Decide between broad release now, hardening first, or limited beta/internal use only.
```

## Notes

- This example is intentionally historical. It captures the repo state on 2026-06-01 before the same-day hardening pass corrected a stale provider-backed transcript test expectation and regenerated `roster.md`.
- The point of the example is not that the repo was permanently unready. The point is that the repo could use its own protocol to surface concrete, falsifiable issues in its own public-facing state.
- If you rerun this prompt against a later checkout, the verdict should be expected to change with the evidence.
