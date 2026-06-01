# Good vs. Bad Verdicts

A verdict is only worth as much as its grounding. The Sovereign Conclave's format can be
filled in two ways: one that earns trust and one that launders a guess into
something that *looks* authoritative. This page shows the difference on the same
decision so the failure mode is unmistakable.

The rule it teaches: **deliberation organizes reasoning; it does not manufacture
truth.** Every load-bearing claim cites the frozen [Evidence Ledger](EVIDENCE_LEDGER.md),
or Marshall flags it.

## The decision (shared)

> Should we ship the new auth rewrite to 100% of users on day one behind a flag?

Use the demo ledger in
[war-game-launch-plan.json](../demos/evidence-ledgers/war-game-launch-plan.json):
E1 (flag-flip is the rollback), E2 (untested above 30% peak), E3 (legacy auth
removed same release), E4 (no support surge plan), E5 (competitor counters within
72h), E6 (the flag depends on the identity service under change).

## Bad verdict (fluent, ungrounded)

> **Recommendation:** Ship it. Feature flags make this safe because you can always
> roll back instantly, and modern auth systems are resilient. Launching fast is
> best practice and the team is clearly capable, so the risk is low. Users expect
> frequent updates and will tolerate minor hiccups.

Why it fails:

- **No citations.** Not one claim points at E1-E6. "Modern auth systems are
  resilient" and "the team is clearly capable" are vibes, not evidence.
- **It contradicts the ledger it ignores.** "Roll back instantly" is exactly the
  claim E6 breaks - the flag depends on the service being changed.
- **It invents comfort.** "Users will tolerate minor hiccups" has no provenance
  and waves away the E4 support gap.
- **It optimizes confidence, not truth.** Fluent, decisive, and wrong. Marshall
  would tag every decisive claim `[UNSUPPORTED]` and the recommendation would be
  demoted before it could be presented as the council's call.

## Good verdict (grounded, dissent preserved)

See the full worked example in
[war-game-launch-plan.md](../demos/verdicts/war-game-launch-plan.md). Its spine:

> **Recommendation:** Do not ship at 100% on day one. Stage the ramp and require
> an independent rollback path that does not traverse the modified identity
> service [E6], a load test to full peak [E2], legacy auth retained until full
> ramp [E3], and a support surge plan [E4].
>
> - **Confidence:** Medium-high - the single point of failure, coverage gap, and
>   irreversibility are supported [E2, E3, E6].
> - **What would change this:** an independent, failure-injection-tested abort
>   path plus full-peak load coverage.
> - **Unresolved dissent:** Zhukov still wants speed and would accept a 25%
>   day-one ramp once the rollback is independent of the identity service.

Why it earns trust:

- **Every decisive claim cites the ledger.** The reader can check each one.
- **It states what it does not know.** Confidence is tied to evidence quality,
  and "What would change this" names the finding that flips the call.
- **It preserves dissent** instead of averaging it into false consensus.
- **It advises; it does not act.** The human still decides.

## The test you can apply in ten seconds

1. Strike every sentence with no `E#`. Is there a recommendation left?
2. For each remaining claim, does the cited row actually say that?
3. Does the verdict say what would change its mind?

A good verdict survives all three. A bad one disappears at step one.
