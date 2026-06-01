# Evidence Ledger

The Evidence Ledger is the frozen factual record for a Conclave run. It is the
line between grounded judgment and fluent guessing.

Every load-bearing factual claim in Round 1, cross-examination, Marshall's
verification, and the final recommendation must cite one or more ledger IDs:
`[E1]`, `[E2]`, `[E1, E4]`. If a claim cannot cite the ledger, it is an
assumption, not evidence.

## Contract

The ledger does four jobs:

1. **Admits evidence:** records which artifacts The Sovereign Conclave may rely on.
2. **Preserves provenance:** records where each artifact came from.
3. **Freezes scope:** prevents seats from inventing facts mid-deliberation.
4. **Enables verification:** lets Marshall tag decisive claims as
   `[SUPPORTED]`, `[UNSUPPORTED]`, or `[CONTESTED]`.

The Sovereign Conclave can reason without much evidence, but it must say confidence is low
and must not present unsupported decisive claims as a recommendation.

## Storage Locations

There are three ledger locations:

| Location | Purpose | Git behavior |
| --- | --- | --- |
| `verdicts/verdict-<UTC-timestamp>.md` | Private generated verdicts with an embedded Markdown ledger. | Ignored except `verdicts/.gitkeep`. |
| `ledgers/*.json` | Private machine-readable ledgers for local runs, automation, and model consumption. | Ignored except `ledgers/.gitkeep`. |
| `demos/evidence-ledgers/*.json` | Public demo ledgers that are safe to commit. | Tracked. |

The actual run ledger should travel with the verdict. For model-native reuse,
also store or export the same evidence as JSON under `ledgers/`.

## Standard Table

Use this shape in verdicts and standalone ledgers:

| ID | Item | Source / provenance | Handling |
| --- | --- | --- | --- |
| E1 | Exact fact, quote, metric, file, screenshot, log excerpt, or source summary. | Where it came from: file path, commit, command, URL, owner, date, meeting, dataset, or user-supplied note. | How to treat it: quoted fact, local file, user assertion, public source, redacted source, contested, stale, partial, etc. |

`ID` must be stable and contiguous from `E1`. Do not renumber items after Round
1 begins.

`Item` should be atomic. One row should support one clear claim. If a file is
large, quote or summarize the exact relevant lines rather than citing "the file"
as if every possible conclusion were proven.

`Source / provenance` should let another reviewer find or reconstruct the input.
For local files, include the path and, where useful, a commit or hash. For public
sources, include the URL and access date. For user assertions, say that they are
user assertions.

`Handling` records the caution label. A row can be real and still limited,
stale, contested, private, or redacted.

## Machine-Readable JSON

Models and tools should prefer the JSON format when available. The schema is:

- [schemas/evidence-ledger.schema.json](../schemas/evidence-ledger.schema.json)

The JSON form has this top-level shape:

```json
{
  "schema_version": "1.0.0",
  "ledger_id": "release-risk-20260601",
  "decision": "Can this release go out?",
  "prepared_by": "local-runner",
  "freeze_time_utc": "2026-06-01T10:21:33Z",
  "ledger_status": "frozen",
  "sensitivity": "internal",
  "entries": [
    {
      "id": "E1",
      "item": "Rollback plan is pending owner approval.",
      "source_type": "user_assertion",
      "source": "--evidence-note",
      "provenance": "User-supplied note at runner invocation",
      "handling": "Treat only as asserted input; do not infer facts beyond the note."
    }
  ],
  "open_evidence_gaps": [],
  "redactions": []
}
```

Each entry uses stable `E#` IDs and must include:

- `id`: stable evidence ID, such as `E1`.
- `item`: the atomic fact, artifact, metric, source summary, file, or quote.
- `source_type`: controlled source class, such as `local_file`,
  `repository_file`, `user_assertion`, `public_url`, `metric`, or `policy`.
- `source`: the concrete source label, path, command, URL, system, or flag.
- `provenance`: who supplied it, when, where it came from, or how to reproduce
  it.
- `handling`: the caution label for use by seats and Marshall.

Optional useful fields include `content_hash`, `uri`, `path`, `observed_at_utc`,
`sensitivity`, and `post_freeze`.

Validation is dependency-free locally: `scripts/validate_repo.py` validates public
demo ledgers, and `bin/conclave --ledger-file ...` validates any ledger it imports.
CI additionally installs `jsonschema` and enforces the published schema for real,
and a sync check keeps the schema and the dependency-free validator from drifting.
`open_evidence_gaps` and `redactions` are required arrays (use `[]` when empty),
matching the schema.

## What Belongs In The Ledger

Good ledger items:

- A pasted requirement, ticket, policy clause, or architectural decision record.
- A local file path plus the exact relevant function, section, or line range.
- A metric with time window, source system, and owner.
- A command output with command, timestamp, and environment.
- A public source with URL, access date, and quoted or summarized claim.
- A user-supplied statement clearly marked as an assertion.
- A screenshot or image with capture date, system, and what it is allowed to
  prove.
- A redacted source where the redaction and confidence impact are explicit.

Bad ledger items:

- "Everyone knows..." with no source.
- "The code probably..." without a file, test, or observed output.
- A whole repository path with no specific claim.
- A URL without the fact it supports.
- A private document described so vaguely that Marshall cannot verify it.
- A model-generated summary treated as primary evidence.

## Freeze Procedure

1. Gather artifacts before any seat argues.
2. Convert them into atomic rows.
3. Assign `E1`, `E2`, `E3` in order.
4. Mark sensitivity and redactions.
5. Freeze the ledger before Round 1.
6. Require every factual claim to cite `E#`.
7. If new evidence arrives later, append it as a post-freeze item and say what
   changed.

Do not edit old rows silently. If a row is wrong, mark it superseded and append
a correcting row. The deliberation record should remain auditable.

## Citation Rules

Use citations directly in claims:

- Good: "The compact route pushes `/civic-stress/counties/:countyId` [E2]."
- Good: "The plan has one incident commander and no deputies [E1]."
- Weak: "The plan has continuity issues [E1]."
- Invalid: "The plan has continuity issues" with no citation.

A citation supports only what the ledger item actually says. If `E1` says a file
exists, it does not prove the file is correct, tested, approved, or complete
unless the row says that too.

## Marshall Verification

Marshall extracts decisive claims and tags them:

- `[SUPPORTED]` means the claim is backed by one or more specific ledger items.
- `[UNSUPPORTED]` means no ledger item backs the claim. Marshall names the
  evidence that would settle it.
- `[CONTESTED]` means ledger items conflict, provenance is weak, or a claim
  depends on unresolved interpretation.

A recommendation whose decisive claims are `[UNSUPPORTED]` must be sent back for
evidence, narrowed, or downgraded in confidence.

## Source Quality

Use the strongest available source:

| Strength | Examples | Handling |
| --- | --- | --- |
| Primary | Repository file, policy text, contract, raw metric, command output, official record | Strongest if current and directly relevant |
| Direct observation | Screenshot, local test output, transcript, meeting note from participant | Useful, but record context and limits |
| Secondary | Analysis, article, summary, third-party report | Use when primary is unavailable; name the dependency |
| Assertion | User statement, stakeholder claim, model summary | Treat as a claim to verify, not settled fact |

Weak sources can still enter the ledger. They just cannot carry more weight than
their provenance supports.

## Confidentiality

Generated verdicts and ledgers may contain sensitive evidence. Keep private
verdicts under `verdicts/` and private JSON ledgers under `ledgers/`; both
directories are git-ignored except for `.gitkeep`.

Rules:

- Do not commit secrets, API keys, credentials, private ledgers, or private
  verdicts.
- Do not paste secret material into public demo files.
- If a source is sensitive, summarize only the allowed fact and mark the row as
  redacted.
- If a claim depends on material that cannot be shown to The Sovereign Conclave, record
  the confidence penalty.

## Runner Support

The local runner can seed a ledger from files and notes:

```bash
bin/conclave \
  --profile risk \
  --evidence-file README.md \
  --evidence-note "Rollback plan is still pending approval from release owner." \
  --stdout "Can this release go out?"
```

`--evidence-file` freezes the file path and a short SHA-256 digest. The runner
does not read the file into the verdict or infer claims from it. Quote the exact
lines before relying on details.

`--evidence-note` freezes an explicit user-supplied note. It proves only that the
note was supplied, not that the underlying world is true.

The runner can also import and export machine-readable ledgers:

```bash
bin/conclave \
  --profile pandemic-preparedness \
  --ledger-file demos/evidence-ledgers/pandemic-preparedness-county-response.json \
  --stdout "Should the county approve the outbreak-response plan as written?"

bin/conclave \
  --validate-ledger demos/evidence-ledgers/pandemic-preparedness-county-response.json

bin/conclave \
  --profile risk \
  --evidence-file README.md \
  --evidence-note "Rollback plan is pending owner approval." \
  --write-ledger ledgers/release-risk.json \
  --stdout "Can this release go out?"
```

`--ledger-file` accepts the JSON schema above and renders its `entries` into the
verdict scaffold. `--validate-ledger` validates a JSON ledger and exits.
`--write-ledger` writes the assembled JSON ledger while still producing the
verdict scaffold. Private output belongs under `ledgers/`.

For manual preparation, use
[demos/evidence-ledger-template.md](../demos/evidence-ledger-template.md).

## Review Checklist

Before Round 1:

- Every likely decisive fact has an `E#`.
- Every `E#` has provenance.
- User assertions are labeled as assertions.
- Redactions and sensitivity are explicit.
- Conflicting sources are both included.
- The null option has enough evidence to be fairly compared.

Before final recommendation:

- Every decisive claim cites `E#`.
- Marshall has tagged supported, unsupported, and contested claims.
- Confidence reflects evidence quality, not seat enthusiasm.
- Missing evidence appears under "What would change this."
