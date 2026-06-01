# Conclave Verdict - Self War-Game: Repo Release Readiness

- **Run ID:** demo-2026-06-01-self-war-game-repo-readiness
- **Convened:** full-conclave (32 seats) + Marshall
- **Profile:** full-conclave

This is a **public historical example**. It preserves the repo self-war-game as it stood on 2026-06-01 before the same-day hardening pass fixed the stale provider-backed transcript test expectation and regenerated `roster.md`.

## 1. The decision

Should Sovereign Conclave be treated as broadly release-ready now, held for hardening first, or limited to caveated beta/internal use only?

Options:

- Ship broadly now as a trustworthy release-ready package.
- Hold broad release; fix the failing provider-backed transcript test and roster/config drift first, then re-validate.
- Keep using it internally or in limited beta, but explicitly downgrade provider-backed and generated-doc claims as experimental until hardened.
- Do nothing.

Optimize for trustworthy external adoption, institutional legitimacy, and maintainability.

## 2. Evidence Ledger (frozen before Round 1)

This is a public historical ledger for a self-inspection run, not a statement about the repo after the later same-day fixes.

| ID | Item | Source / provenance | Handling |
| --- | --- | --- | --- |
| E1 | README presents Sovereign Conclave as an evidence-grounded deliberation protocol package with 33 active seats, 24 profiles, installer, local runner, and curated demos. | README.md. | Public project claim; use as release-facing representation. |
| E2 | The standing directives require evidence before opinion, forced dissent, advice-only output, env-only provider routing, and frozen-ledger discipline. | directives.md. | Authoritative project governance rule. |
| E3 | `scripts/validate_repo.py` enforces frontmatter, path, model, footer, profile, provider-config, demo verdict, and demo ledger invariants. | scripts/validate_repo.py. | Repository code; authoritative on structural validation scope. |
| E4 | `scripts/provider_runner.py` makes provider mode opt-in and env-only, and records advocate Round 1 calls, Justice checks, Marshall verification, and synthesis in the transcript. | scripts/provider_runner.py. | Repository code; authoritative on provider-backed runner behavior. |
| E5 | `configs/conclave-roster.json` declares 33 seats, 24 profiles, 22 polarity pairs, and `full-conclave` as 32 listed seats plus Marshall. | configs/conclave-roster.json. | Machine-readable source of truth for roster/profile makeup. |
| E6 | Running `python3 scripts/validate_repo.py` passed with `Validation passed` and `seats=33 profiles=24 polarity_pairs=22 demo_ledgers=3 schema_enforced=False`. | Observed terminal output on 2026-06-01. | Historical command output; applies to the repo state at the time of the run. |
| E7 | Running `python3 -m unittest discover -s tests` failed 1 of 26 tests: `test_transcript_is_captured` expected `len(data["calls"]) == 6` but actual was 8. | Observed terminal output on 2026-06-01. | Historical command output; captures the pre-hardening failing state. |
| E8 | `tests/test_provider_runner.py` hardcoded the old expectation with the comment `3 advocates + 1 justice + 1 verifier + 1 synthesis for the risk profile.` | tests/test_provider_runner.py. | Repository test file; direct evidence of the stale expectation present at that time. |
| E9 | The current `risk` profile contained 4 advocates and 2 justices, and `provider_runner.py` looped separately over advocates, justices, verifier, and synthesis, implying 8 transcript calls. | configs/conclave-roster.json + scripts/provider_runner.py. | Mechanistic inference from source code and config. |
| E10 | Running `python3 scripts/generate_roster.py --check` reported `roster.md is out of sync with configs/conclave-roster.json`, including divergent quorum wording and profile table content. | Observed terminal output on 2026-06-01. | Historical command output; captures the generated-file drift present at that time. |
| E11 | `bash -n install.sh` passed and `./install.sh --target all --dry-run` showed copy-only writes for agents, docs, configs, schemas, demos, and skill files into Claude, Codex, and Antigravity directories. | Observed terminal output on 2026-06-01. | Historical command output; evidence about installer behavior on that repo state. |
| E12 | SECURITY.md names secret disclosure, unsafe installer behavior, misleading unsupported claims, and provider-routing misuse as the main repo risks; provider mode is off by default and env-only. | SECURITY.md. | Authoritative public risk model. |
| E13 | SKILL.md requires blind Round 1, convergence check, Round 2 cross-examination, a counterfactual pass on premature convergence, and writing a verdict file before chat output. | SKILL.md. | Authoritative protocol contract for the full `/conclave` skill. |
| E14 | docs/RUNNER.md says provider mode runs blind Round 1, Justice checks, Marshall verification, and neutral synthesis; it does not claim the full SKILL.md cross-examination flow. | docs/RUNNER.md. | Public documentation; explicit scope statement for the runner implementation. |

> Every factual claim below references the frozen ledger or is treated as an assumption.

## 3. Positions (Round 1 - blind)

- **conclave-zhukov:** Hold broad release, fix fast, then ship; known visible faults are trivial to repair but should not be met by first-contact users [E6, E7, E9, E10].
- **conclave-washington:** Hold broad release; trust breaks if outsiders first meet a failing test and stale generated file [E1, E7, E9, E10].
- **conclave-pershing:** Hold; release should follow readiness checks, not precede them [E7, E8, E9, E10].
- **conclave-giap:** Limited beta/internal use only; the repo should avoid fighting on broad-public terrain until drift is removed [E1, E7, E9, E10].
- **conclave-yi-sun-shin:** Hold; do not seek external adoption from compromised ground [E7, E9, E10].
- **conclave-mcchrystal:** Hold, repair, then ship; the defects are small but externally visible [E6, E7, E10, E11, E12].
- **conclave-lee-kuan-yew:** Hold broad release; the defects are cheap to fix and not worth compounding into a trust problem [E6, E7, E10, E12].
- **conclave-augustus:** Hold; public legitimacy requires config, generated docs, and tests to align [E6, E7, E9, E10].
- **conclave-suleiman:** Hold; the codified rules and release-facing artifacts must match [E7, E9, E10].
- **conclave-elizabeth:** Hold broad release; do not spend credibility before the public surface is aligned [E6, E7, E9, E10].
- **conclave-sejong:** Hold; ordinary adopters should not inherit obvious trust barriers [E6, E7, E10].
- **conclave-mandela:** Hold; do not ask outsiders to inherit avoidable ambiguity [E6, E7, E9, E10].
- **conclave-toussaint:** Hold; do not ask adopters to trust a repo that knows its own public record is drifting [E1, E7, E10, E12].
- **conclave-obama:** Hold; broad adoption requires claims that match observable behavior [E7, E10].
- **conclave-bush:** Hold; continuity and trust are better protected by a short hardening pass [E6, E7, E9, E10].
- **conclave-cheney:** Hold; public contradictions in the command record and docs corrode trust faster than delay does [E6, E7, E9, E10].
- **conclave-hayden:** Hold; the hidden risk is a credibility gap between what the repo says and what outsiders can verify [E7, E10].
- **conclave-authoritarian:** Hold; the repo currently projects more procedural order than it proves [E7, E9, E10].
- **conclave-addington:** Hold; the public record and enforcement surface are internally inconsistent [E7, E9, E10].
- **conclave-maathai:** Hold; stewardship requires repair before distribution [E1, E7, E10].
- **conclave-colonial-administrator:** Hold; broad release now would shift reconciliation costs onto adopters [E7, E9, E10].
- **conclave-mau-mau:** Hold; do not ship false promises and ask users to absorb the breach [E7, E10, E12].
- **conclave-feynman:** Hold; the failure and drift are mechanically explainable and should be fixed before any release-ready claim [E7, E9, E10].
- **conclave-aurelius:** Hold; take the lower-downside path and harden first [E6, E7, E10].
- **conclave-von-neumann:** Hold; expected trust loss from known contradictions exceeds the value of shipping now [E6, E7, E9, E10].
- **conclave-oppenheimer:** Hold; governance evidence and generated artifacts should agree before broad adoption [E7, E10].
- **conclave-sun-tzu:** Hold; avoid opening on terrain already weakened by an easy credibility attack [E7, E9, E10].

## 4. Cross-examination (Round 2)

Round 1 converged early on the same recommendation, so the protocol's forced-dissent rule was triggered [E13]. The strongest counterfactual against the front-runner came from **Elizabeth (counterfactual)**: because provider mode is opt-in, off by default, env-only, and documented more narrowly than the full protocol, a caveated beta/internal posture might preserve tempo and learning without overclaiming broad readiness [E4, E6, E11, E12, E14].

Cross-examination narrowed the dispute. The key question was not whether the repo was fundamentally unsound. It was whether the narrower, opt-in status of provider mode was already enough to justify recommending limited beta/internal use. Giáp and the counterfactual case argued yes, because the default local path was stronger than the provider-backed path and the defects were bounded [E4, E6, E11, E12, E14].

Most advocates challenged that sufficiency leap, not its premises. They argued that a known failing test and a generated-file drift already make the public record contradictory, so even a caveated beta posture risks asking outsiders to absorb contradictions the maintainer already knows how to repair [E7, E9, E10, E12].

The Justice seats imposed structural bounds rather than picking a winner:

- **Lady Hale:** any release claim must be proportionate to what the current artifacts actually verify [E1, E7, E9, E10, E12].
- **Bhagwati:** downstream adopters bear the cost of misplaced trust, so broad readiness cannot rest on internal validation alone while known trust defects remain [E1, E7, E10, E12].
- **Chaskalson:** public integrity is violated if evidence-grounded rigor is claimed more broadly than verified artifacts support [E1, E2, E7, E9, E10, E12].
- **Jackson:** any release posture must be explicitly limited to what is verified; urgency or learning value cannot excuse overbroad claims [E2, E4, E7, E10, E12, E14].
- **Sachs:** either repair the trust injuries or plainly narrow claims to the validated opt-in surface; do not compound the harm [E4, E7, E9, E10, E12, E14].

## 5. Verification (Marshall)

- `[SUPPORTED]` Broad release is not grounded while 1 of 26 tests is failing in the provider-backed transcript path <- E7, E8, E9.
- `[SUPPORTED]` A release-facing roster/config mismatch exists <- E5, E10.
- `[SUPPORTED]` The repo publicly presents a broad, rigorous package, not only the narrowed provider path <- E1, E13, E14.
- `[SUPPORTED]` The surfaced defects should be fixed before broad-release reconsideration, and the existing validation surface should then be rerun <- E3, E6, E7, E10.
- `[SUPPORTED]` Provider mode is opt-in, env-only, and off by default <- E4, E12.
- `[SUPPORTED]` Provider mode is narrower than the full SKILL workflow <- E13, E14.
- `[UNSUPPORTED]` Those narrower, opt-in characteristics are sufficient to make limited beta/internal use acceptable despite the known failing test and roster drift. Marshall's note: the premises are supported, but the sufficiency leap is not. It would be settled by explicit beta-only positioning and acceptance criteria that narrowly tolerate those defects.
- **Directive check:** Pass for the hardening-hold recommendation. A beta recommendation would violate the evidence-before-opinion rule on this ledger because its sufficiency claim is unsupported [E2].

## 6. Recommendation

The Sovereign Conclave advised choosing the hardening-first path: do not treat the repo as broadly release-ready yet; repair the failing provider-backed transcript-count test and regenerate `roster.md` from `configs/conclave-roster.json`, then rerun the validation stack before reassessing public readiness.

The important point in this public example is not permanent unfitness. It is that the repo could use its own protocol to surface concrete, falsifiable problems in its own outward-facing state. The ledger supported a narrower fact than broad-release readiness: the repo already had serious structure, disciplined installer behavior, and a safer default/offline path than the provider-backed path [E4, E6, E11, E12, E14]. But the ledger did not support making that narrower fact into the conclave's recommendation for caveated beta/internal use, because the release-facing materials did not yet supply explicit beta-only caveats and acceptance criteria [E12].

- **Confidence:** Medium. The decisive claims for the hardening-first recommendation were fully supported, but the ledger left open whether a properly documented beta posture could have been justified with more evidence.
- **What would change this:** Either fix the failing test and sync the generated roster, then rerun validation cleanly; or add explicit beta-only positioning and acceptance criteria that narrowly bind what is being claimed.
- **Unresolved dissent:** Giáp and the D-3 counterfactual case argued that a narrow, caveated beta/internal posture might preserve tempo because provider mode was opt-in, off by default, and narrower than the full protocol [E4, E12, E14]. Marshall found that premise supported but its sufficiency unsupported on the historical ledger.

## 7. Decision (human)

<Left blank. The Sovereign Conclave advises; you decide, and you own the call.>
