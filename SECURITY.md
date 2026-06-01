# Security Policy

Sovereign Conclave is a prompt/protocol repository, installer, and set of agent
instructions. It is not a hosted service. The main security risks are accidental
secret disclosure, unsafe installer behavior, misleading unsupported claims, and
misuse of optional cross-provider model routing.

## Supported Versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Reporting a Vulnerability

Do not open public issues for vulnerabilities that include secrets, private
paths, private prompts, credentials, or sensitive evidence ledgers.

Preferred reporting path:

1. If this repository is hosted on GitHub, open a private security advisory.
2. If private advisories are unavailable, contact the maintainer out of band and
   include only the minimum reproduction details needed.
3. Publicly disclose only after a fix or mitigation is available.

Expected response target: acknowledge within 7 days and publish a mitigation or
status update within 30 days for confirmed issues.

## Sensitive Data Guidance

- Do not commit API keys, provider credentials, private evidence ledgers, or
  generated verdicts that contain confidential data.
- Optional model/provider credentials must come from environment variables, not
  repository files.
- Treat pasted user evidence as sensitive by default.
- If a verdict must be shared, remove private identifiers, credentials, tokens,
  and proprietary source excerpts first.

## Installer Security

- `install.sh --dry-run` should show planned filesystem writes before install.
- The installer should not modify shell startup files, credential stores, or
  provider configuration.
- New install targets must copy only repository-owned skill, agent, config, and
  documentation files.

## Model and Provider Risk

Cross-model routing can reduce shared blind spots, but it may send evidence to
multiple providers. Users are responsible for matching provider use to their
data-handling requirements.

The opt-in provider mode (`bin/conclave --provider-run`) is off by default and
reads credentials only from environment variables (`CONCLAVE_PROVIDER_CMD` or
`ANTHROPIC_API_KEY`); it never reads keys from files and never writes them to
transcripts. Run transcripts can contain evidence and model output, so they are
written under git-ignored `verdicts/`.

## Scope

In scope:

- Installer behavior.
- Prompt files that encourage unsafe action, credential exposure, or
  unsupported claims.
- Configuration examples that risk committing secrets.
- Documentation that could mislead users about privacy or authority.

Out of scope:

- Security properties of third-party model providers.
- User-created verdicts or evidence ledgers outside this repository.
- Local assistant runtimes not distributed by this project.
