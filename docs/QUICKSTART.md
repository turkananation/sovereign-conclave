# Quickstart

This gets Sovereign Conclave from clone to first verdict scaffold in a few
minutes.

## 1. Install a tagged release

For a stable install, start from the signed `0.1.0` release tag:

```bash
git clone https://github.com/turkananation/sovereign-conclave.git
cd sovereign-conclave
git checkout 0.1.0
./install.sh --target codex
```

Use `./install.sh`, `./install.sh --target claude`, or
`./install.sh --target antigravity` for the other supported tools.
Restart the target tool after installing.

## 2. Validate the checkout

```bash
python3 scripts/validate_repo.py
python3 scripts/generate_roster.py --check
python3 -m unittest discover -s tests
bash -n install.sh
./install.sh --target all --dry-run
```

The validator checks the machine-readable roster, agent files, Markdown roster,
profiles, model slots, schema/validator agreement, and required docs. The roster
check confirms `roster.md` is still generated from `configs/conclave-roster.json`.

## 3. Install from an existing checkout

Claude Code remains the default target:

```bash
./install.sh
```

Other targets:

```bash
./install.sh --target codex
./install.sh --target antigravity
```

Restart the target tool after installing. To remove it again:

```bash
./install.sh --uninstall --target all
```

## 4. Run a Conclave in an assistant

Use `/conclave` where slash commands are available:

```text
/conclave --profile architecture Should we split the analytics service out of the monorepo?
/conclave --profile war-game Pressure-test the county incident response plan.
/conclave --profile esiasa-civic-stress Should compact county dossiers stay route-backed on mobile?
```

Paste or attach the real artifacts before Round 1. Those artifacts become the
[Evidence Ledger](EVIDENCE_LEDGER.md). Keep ledger rows atomic and provenance-bearing:
one concrete fact, file, quote, metric, command output, or user assertion per
`E#`.

## 5. Use the local runner scaffold

The local runner does not call model providers. It selects seats and creates a
verdict scaffold that can be filled by an assistant or future provider-backed
runner.

```bash
bin/conclave --list-profiles
bin/conclave --profile pandemic-preparedness --dry-run "County outbreak readiness plan"
bin/conclave --profile architecture --stdout "Move notifications off Cloud Run?"
bin/conclave --profile risk --evidence-file README.md --evidence-note "Rollback plan is pending owner approval." --stdout "Can this release go out?"
bin/conclave --profile pandemic-preparedness --ledger-file demos/evidence-ledgers/pandemic-preparedness-county-response.json --stdout "Approve the county outbreak-response plan?"
bin/conclave --validate-ledger demos/evidence-ledgers/pandemic-preparedness-county-response.json
bin/conclave --profile risk --evidence-file README.md --write-ledger ledgers/release-risk.json --stdout "Can this release go out?"
```

By default, generated scaffolds are written to `verdicts/`, which is ignored
except for `.gitkeep` because verdicts may contain sensitive evidence.
Private machine-readable ledgers belong under `ledgers/`, which is also ignored
except for `.gitkeep`.

Use [demos/evidence-ledger-template.md](../demos/evidence-ledger-template.md)
when preparing evidence outside the runner.

## 6. Read the examples

- [demos/verdicts/architecture-notifications-platform-split.md](../demos/verdicts/architecture-notifications-platform-split.md)
- [demos/verdicts/war-game-launch-plan.md](../demos/verdicts/war-game-launch-plan.md)
- [demos/verdicts/esiasa-civic-stress-route-backed-dossier.md](../demos/verdicts/esiasa-civic-stress-route-backed-dossier.md)
- [demos/verdicts/pandemic-preparedness-county-response.md](../demos/verdicts/pandemic-preparedness-county-response.md)

They show the intended output standard: clear decision, frozen evidence, real
disagreement, Marshall verification, and advice rather than action. See
[GOOD_VS_BAD_VERDICTS.md](GOOD_VS_BAD_VERDICTS.md) for why grounding beats a
fluent guess.
