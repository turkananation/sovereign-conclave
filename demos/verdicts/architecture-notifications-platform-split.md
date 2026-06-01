# Conclave Verdict - Notifications Service Platform Split

- **Run ID:** demo-2026-06-01-architecture-notifications
- **Convened:** conclave-feynman, conclave-lee-kuan-yew, conclave-von-neumann, conclave-oppenheimer + conclave-marshall
- **Profile:** architecture

## 1. The decision

Should we extract the notifications service out of the shared monolith now, into its own service and datastore?

Options:

- Extract now in one project.
- Extract in phases, decoupling the datastore behind a reversible migration first.
- Do nothing and keep notifications inside the monolith.

Optimize for incident reduction, deploy throughput, and sustainable operation by a small team.

## 2. Evidence Ledger (frozen before Round 1)

This is a public demo ledger, not a live production file.

| ID | Item | Source / provenance | Handling |
| --- | --- | --- | --- |
| E1 | Notifications shares the monolith Postgres; 3 of the last 5 Sev2 incidents traced to notification fan-out saturating the shared connection pool. | Sample incident-review export. | Public demo input; correlation stated, deeper root cause unknown. |
| E2 | Notifications is ~9% of deploys but its shared pipeline stage blocks every release for ~40 minutes. | Sample CI pipeline metrics. | Public demo input; proves only the sample pipeline state. |
| E3 | Proposed split extracts notifications to its own service, datastore, and queue; ~6 engineer-weeks, no owner assigned. | Sample architecture decision record draft. | Public demo input; estimate unvalidated, ownership open. |
| E4 | Current p99 notification send latency is 4.2s at peak against a 2s SLO. | Sample latency dashboard. | Public demo input; single-window measurement. |
| E5 | The owning team is 4 engineers and the on-call rotation is already at capacity. | Team lead statement. | Public demo input; asserted staffing claim, not an audited model. |
| E6 | The split's rollback is "dual-write then cut over", with no tested rollback for the datastore migration step. | Sample architecture decision record draft. | Public demo input; absent tested rollback treated as open risk. |

> Every claim below references the frozen ledger.

## 3. Positions (Round 1 - blind)

- **conclave-feynman:** Name the mechanism before betting on the fix. The Sev2s correlate with a saturated shared connection pool [E1], and a private datastore removes that coupling - but the pool-as-bottleneck claim is still correlation; demand the trace or load test that isolates it before committing six weeks [E1, E4].
- **conclave-lee-kuan-yew:** The split is right long-term but unsustainable as staffed. Six engineer-weeks on a 4-person team already at on-call capacity, with no owner, will stall or burn the team [E3, E5]. Phase it so it survives contact with reality.
- **conclave-von-neumann:** Model the payoff. Splitting clears the shared-pipeline block [E2] and pool contention [E1], but the unowned, untested datastore rollback [E6] is the dominated branch: low probability, catastrophic cost. Minimax says do not cut over without a tested rollback.
- **conclave-oppenheimer:** The datastore migration is the irreversible step [E6]. "Dual-write then cut over" hides risk behind apparent reversibility; ask who owns the cutover and whether it can actually be recalled before treating it as safe.

## 4. Cross-examination (Round 2)

Lee Kuan Yew challenged Feynman: even a correct mechanism does not justify a project a 4-person team cannot staff without dropping on-call [E5]. Feynman's measurement demand survived as a precondition, not a blocker.

von Neumann and Oppenheimer converged on E6 from different directions - expected-value dominance and irreversibility - so a counterfactual pass was run: the strongest case *for* an immediate full split is that prolonged coupling keeps producing Sev2s [E1] and the pipeline tax compounds [E2]. That case is real but does not cure the untested rollback [E6].

## 5. Verification (Marshall)

- `[SUPPORTED]` Notification fan-out is implicated in 3 of 5 recent Sev2s via the shared pool <- E1.
- `[SUPPORTED]` The shared pipeline stage blocks releases for ~40 minutes <- E2.
- `[SUPPORTED]` p99 send latency (4.2s) exceeds the 2s SLO <- E4.
- `[UNSUPPORTED]` Six engineer-weeks is sufficient - would be settled by: a scoped plan with an assigned owner and a rollback test budget; E3 is an unvalidated estimate.
- `[CONTESTED]` "Dual-write then cut over" is a safe rollback - E6 states no datastore rollback has been tested.
- **Directive check:** Pass. The recommendation is advice to the human; it authorizes no migration.

## 6. Recommendation

Extract in phases. Decouple the notifications datastore behind a tested, reversible migration first; do not cut over until a tested datastore rollback and a named owner exist [E3, E6].

Sequence:

1. Assign an owner and a rollback-test budget before any extraction work [E3].
2. Isolate and confirm the connection-pool bottleneck with a trace or load test [E1, E4].
3. Move notifications off the shared deploy stage to recover release throughput [E2].
4. Migrate the datastore only behind a tested, reversible cutover [E6].

- **Confidence:** Medium. The coupling costs are well supported [E1, E2, E4], but the plan's feasibility and rollback safety are not [E3, E5, E6].
- **What would change this:** A tested datastore rollback plus an assigned owner would raise confidence and could justify a single-project split; evidence that the pool is *not* the bottleneck would shrink the expected benefit.
- **Unresolved dissent:** von Neumann would gate the cutover even harder on the rollback test; Lee Kuan Yew would not start until the team is backfilled.

## 7. Decision (human)

<Left blank. The Sovereign Conclave advises; you decide, and you own the call.>
