# Quickstart

This gets Sovereign Conclave from clone to first verdict scaffold in a few
minutes.

## 1. Validate the checkout

```bash
python3 scripts/validate_repo.py
bash -n install.sh
./install.sh --target all --dry-run
```

The validator checks the machine-readable roster, agent files, Markdown roster,
profiles, model slots, and required docs.

## 2. Install for your tool

Claude Code remains the default target:

```bash
./install.sh
```

Other targets:

```bash
./install.sh --target codex
./install.sh --target antigravity
```

Restart the target tool after installing.

## 3. Run a Conclave in an assistant

Use `/conclave` where slash commands are available:

```text
/conclave --profile architecture Should we split the analytics service out of the monorepo?
/conclave --profile war-game Pressure-test the county incident response plan.
/conclave --profile esiasa-civic-stress Should compact county dossiers stay route-backed on mobile?
```

Paste or attach the real artifacts before Round 1. Those artifacts become the
Evidence Ledger.

## 4. Use the local runner scaffold

The local runner does not call model providers. It selects seats and creates a
verdict scaffold that can be filled by an assistant or future provider-backed
runner.

```bash
bin/conclave --list-profiles
bin/conclave --profile pandemic-preparedness --dry-run "County outbreak readiness plan"
bin/conclave --profile architecture --stdout "Move notifications off Cloud Run?"
```

By default, generated scaffolds are written to `verdicts/`, which is ignored
except for `.gitkeep` because verdicts may contain sensitive evidence.

## 5. Read the examples

- `demos/verdicts/esiasa-civic-stress-route-backed-dossier.md`
- `demos/verdicts/pandemic-preparedness-county-response.md`

They show the intended output standard: clear decision, frozen evidence, real
disagreement, Marshall verification, and advice rather than action.
