# Evidence Ledger Template

Use this when preparing a Conclave run outside the local runner. Keep entries
atomic: one cited artifact, quote, metric, observation, or source per row.

**Decision:** <one-sentence decision question>
**Prepared by:** <name / role>
**Freeze time:** <UTC timestamp>
**Ledger status:** Frozen before Round 1
**Sensitivity:** <public / internal / confidential / secret-derived-not-quoted>

| ID | Item | Source / provenance | Handling |
| --- | --- | --- | --- |
| E1 | <Exact fact, quote, file path, metric, screenshot, log excerpt, or source summary.> | <Where it came from, who supplied it, date, commit, URL, file path, or command.> | <How to treat it: quote exact text, local file, user assertion, redacted source, contested, stale, partial, etc.> |
| E2 | <Next atomic item.> | <Source / provenance.> | <Handling note.> |

## Open Evidence Gaps

- <What decisive claim cannot yet be supported?>
- <What artifact would settle it?>

## Redactions

- <What was redacted, why, and whether the redaction weakens confidence?>

## Freeze Rule

After Round 1 begins, do not silently add, edit, or renumber ledger items. If new
evidence arrives, append `E-next`, mark it as post-freeze, and state which
claims or confidence levels changed because of it.
