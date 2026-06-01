# Contributing

Contributions are welcome when they strengthen the Conclave's reliability,
portability, or evidence discipline.

## Core Rules

- A seat is a lens, not a capability. Do not imply that a name gives the model a
  historical figure's skill.
- Add a seat only when it argues a stance or structural check no existing seat
  covers.
- Marshall stays opinion-free and is always convened.
- Justice seats are structural checks, not advocates.
- The Conclave advises; the human decides.
- Secrets, API keys, private evidence ledgers, and confidential verdicts must
  not be committed.

## Seat Proposal Checklist

Every advocate seat must include:

- Frontmatter with `name`, `description`, and `model`.
- One clear stance.
- Three or four concrete "How you argue" moves.
- A characteristic bias.
- A `You are NOT` boundary.
- A polarity partner.
- The standard Evidence Ledger footer.

Every Justice seat must include:

- Frontmatter with `name`, `description`, and `model`.
- A distinct structural check.
- Clear scope boundaries.
- No preference about which option wins.
- The standard Evidence Ledger footer, unless it is Marshall's special verifier
  file.

## Development Checks

Before opening a pull request, run:

```bash
python3 scripts/validate_repo.py
bash -n install.sh
git diff --check
./install.sh --target all --dry-run
```

When validation scripts are added, they become required for pull requests.

## Commit Style

Use small, descriptive commits. Good examples:

- `docs: add security policy`
- `chore: add BSD-3-Clause license`
- `agents: add continuity preparedness seat`
- `installer: support codex target`

## Review Standard

Reviews should prioritize:

- Broken protocol invariants.
- Unsupported capability claims.
- Installer safety.
- Documentation that could cause users to over-trust unsupported claims.
- Roster/profile changes that make quorums too large or too similar.
