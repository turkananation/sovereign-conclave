# Conclave Verdict - War-Game: Auth Rewrite Launch Plan

- **Run ID:** demo-2026-06-01-war-game-launch-plan
- **Convened:** conclave-zhukov, conclave-sun-tzu, conclave-giap, conclave-lady-hale + conclave-marshall
- **Profile:** war-game

Cells:

- **Blue (defends the plan):** conclave-zhukov.
- **Red (adversary, free to win):** conclave-sun-tzu + conclave-giap.
- **White (adjudicates grounding, injects events):** conclave-marshall + conclave-lady-hale.

## 1. The decision

Should we ship the new auth rewrite to 100% of users on day one behind a feature flag next week?

Options:

- Ship at 100% on day one behind the flag.
- Ship as a staged ramp (1% -> 25% -> 100%) with an independent rollback path.
- Do nothing and hold the launch.

Optimize for a survivable launch: reliability, a real abort path, and rights-respecting treatment of locked-out users.

## 2. Evidence Ledger (frozen before Round 1)

This is a public demo ledger, not a live launch file.

| ID | Item | Source / provenance | Handling |
| --- | --- | --- | --- |
| E1 | Plan enables new auth for 100% of users on day one behind a flag; rollback is to flip the flag off. | Sample launch plan. | Public demo input; proves only the sample plan state. |
| E2 | The new auth path is not load tested above 30% of projected peak. | Sample load-test summary. | Public demo input; coverage gap directly stated. |
| E3 | Legacy auth is removed from the build in the same release; no fallback beyond 7 days. | Sample launch plan. | Public demo input; post-window irreversibility is a constraint. |
| E4 | Support is staffed for normal volume with no surge plan for auth lockouts. | Support lead statement. | Public demo input; asserted staffing claim. |
| E5 | The competitor launched a counter-promo within 72h of each of our last three launches. | Sample market-history note. | Public demo input; three-event pattern, not a guarantee. |
| E6 | The feature-flag system depends on the same identity service the auth rewrite modifies. | Sample dependency manifest. | Public demo input; shared dependency is the central abort-path risk. |

> Every claim below references the frozen ledger.

## 3. Positions (Round 1 - blind)

- **conclave-zhukov (Blue):** Ship decisively. The flag gives an instant rollback [E1], and a fast 100% launch seizes the window before the competitor's known 72h counter-move [E5]. Hesitation cedes the initiative.
- **conclave-sun-tzu (Red):** The abort path is an illusion. The flag depends on the very identity service the rewrite changes [E6]; if that service degrades, flipping the flag does not save you. We win by attacking the assumption of a clean retreat, not the launch itself.
- **conclave-giap (Red):** We will not fight you at the strong point. We protract: a 72h counter-promo [E5] plus a slow trickle of auth lockouts into an unstaffed support line [E4] exhausts you and forces a panic rollback - after legacy auth is already gone from the build [E3].
- **conclave-lady-hale (White):** A 100%-day-one flip puts the full burden of any defect on every locked-out user at once [E1, E4]. A staged ramp is the less-restrictive means to the same legitimate aim; the plan must justify why it is not used.

## 4. Cross-examination (Round 2)

Red dismantled Blue's core claim: Zhukov's "instant rollback" [E1] is not independent of the failure it must answer, because the flag shares the modified identity service [E6]. Zhukov's initiative argument [E5] survived only as a reason to launch *soon*, not to launch at 100%.

White injected an event: identity-service latency rises under a competitor-driven traffic spike. Under that injection, Blue had no abort that does not traverse the degraded dependency [E6], and no surge capacity to hold the line [E4]. With legacy auth removed [E3], the plan reaches an unrecoverable state.

## 5. Verification (Marshall)

- `[SUPPORTED]` The flag system shares the identity service under change <- E6.
- `[SUPPORTED]` The new path is unproven above 30% of peak <- E2.
- `[SUPPORTED]` Legacy auth is removed in the same release <- E3.
- `[SUPPORTED]` The competitor has countered within 72h three times <- E5.
- `[CONTESTED]` "Flip the flag" is a safe rollback - E1 asserts it; E6 shows the abort path depends on the degraded component.
- **Directive check:** Pass. The verdict recommends a plan to the human; it authorizes no deploy.

## 6. White-cell outcome

As written, **Red wins the engagement.** The plan has a single point of failure on the abort path [E6], no surge capacity [E4], and an irreversible legacy removal [E3]; a plausible, evidence-backed Red campaign forces an unrecoverable state. The plan loses not on the launch but on the retreat.

## 7. Recommendation

Do not ship at 100% on day one. Ship as a staged ramp (1% -> 25% -> 100%) and require, before ramping:

1. An independent rollback path that does not traverse the modified identity service [E6].
2. A load test to at least 100% of projected peak [E2].
3. Legacy auth retained in the build until the new path holds at full ramp [E3].
4. A support surge plan for an auth-lockout spike [E4].

- **Confidence:** Medium-high. The single point of failure, coverage gap, and irreversibility are all supported [E2, E3, E6]; the competitor pattern is suggestive [E5].
- **What would change this:** An independent, failure-injection-tested abort path plus full-peak load coverage would justify a faster ramp.
- **Unresolved dissent:** Zhukov still wants speed and would accept a 25% day-one ramp once the rollback path is independent of the identity service.

## 8. Decision (human)

<Left blank. The Sovereign Conclave advises; you decide, and you own the call.>
