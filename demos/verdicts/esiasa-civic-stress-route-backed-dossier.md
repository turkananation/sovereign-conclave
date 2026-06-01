# Conclave Verdict - eSiasa Civic Stress Route-Backed Dossier

- **Run ID:** demo-2026-06-01-esiasa-civic-stress
- **Convened:** conclave-mcchrystal, conclave-hayden, conclave-maathai, conclave-atkinson, conclave-bhagwati + conclave-marshall
- **Profile:** esiasa-civic-stress

## 1. The decision

Should eSiasa keep route-backed compact county dossiers as the mobile default for Civic Stress full-record viewing, while preserving richer desktop/tablet detail behavior?

Options:

- Keep the route-backed compact dossier pattern.
- Revert compact mobile to dialog or inline detail.
- Do nothing and leave behavior inconsistent across layouts.

Optimize for mobile reliability, operator trust, auditability, and civic-stress decision usefulness.

## 2. Evidence Ledger (frozen before Round 1)

| ID | Item | Source / provenance | Handling |
| --- | --- | --- | --- |
| E1 | The Civic Stress compact county dossier was converted from inline/dialog detail to a dedicated route-backed mobile flow. | Prior eSiasa rollout summary. | Demo uses prior rollout evidence; live code should be rechecked before a real decision. |
| E2 | Compact/mobile county taps now push `/civic-stress/counties/:countyId`; non-compact layouts preserve richer desktop/tablet behavior. | Prior eSiasa rollout summary. | Demo uses prior rollout evidence; routing state may drift. |
| E3 | `CivicStressCountyDossierScreen` renders the route-backed compact dossier with page header, back action, refresh action, and county detail. | Prior eSiasa rollout summary. | Demo uses prior rollout evidence; UI details should be verified in current code. |
| E4 | `AdminCountyIntelligenceContentView` accepts `dossierCountyId`; when present it loads dossier detail directly. | Prior eSiasa rollout summary. | Demo uses prior rollout evidence; direct loading behavior should be tested live. |
| E5 | A compact county brief chip overflow was fixed by constraining label and value with `Flexible`. | Prior eSiasa rollout summary. | Demo uses prior rollout evidence; screen-size coverage is bounded by the cited tests. |
| E6 | Validation passed with focused mobile navigation/router tests, full `esiasa_admin` verification, and `git diff --check`. | Prior eSiasa rollout summary. | Demo uses prior rollout evidence; test results may be stale. |

> Every claim below references the frozen ledger.

## 3. Positions (Round 1 - blind)

- **conclave-mcchrystal:** Keep the route-backed pattern, because mobile operators need a shared navigation contract rather than layout-specific improvisation; the direct route and `dossierCountyId` create a repeatable operating path [E2, E4].
- **conclave-hayden:** Keep it, but treat dossier routing as an intelligence surface: route access, refresh behavior, and audit events should be visible enough to detect stale or misused county intelligence [E3, E4].
- **conclave-maathai:** Keep it if the dossier improves local legitimacy: county-level stress data must be reachable on the devices and contexts closest to communities, and the compact overflow fix matters because cramped UI can hide civic risk [E2, E5].
- **conclave-atkinson:** Keep it, because a route-backed dossier gives a clearer recordable path than dialogs for full-record viewing; the direct route and router coverage strengthen accountability [E2, E4, E6].
- **conclave-bhagwati:** Keep it only if affected operator groups are represented in tests and evidence. The ledger proves route behavior and overflow remediation, but not whether county operators or low-bandwidth field users validated the flow [E5, E6].

## 4. Cross-examination (Round 2)

Atkinson challenged Hayden: intelligence-surface concerns should not block the route pattern because the ledger already shows the route is explicit and test-covered [E2, E6]. Hayden's concern survived only as a follow-up instrumentation requirement, not a reason to revert.

Bhagwati challenged McChrystal and Atkinson: the ledger proves technical routing, but not field-operator acceptance. That dissent survives because no ledger item contains user research or field feedback [E1-E6].

Maathai challenged a narrow "tests passed" interpretation: the overflow fix is not cosmetic; it is part of whether county stress information remains legible on compact devices [E5].

## 5. Verification (Marshall)

- `[SUPPORTED]` Compact county taps push the route-backed dossier path <- E2.
- `[SUPPORTED]` The dossier screen and direct `dossierCountyId` loading exist <- E3, E4.
- `[SUPPORTED]` A narrow mobile overflow was fixed and validated <- E5, E6.
- `[UNSUPPORTED]` Field operators prefer the route-backed flow - would be settled by: usability sessions, support tickets, or analytics comparing completion and backtracking.
- `[UNSUPPORTED]` The route has sufficient audit telemetry - would be settled by: event names, audit log records, or analytics payload evidence.
- **Directive check:** Pass. The verdict recommends a pattern to the human; it does not authorize deployment.

## 6. Recommendation

Keep route-backed compact county dossiers as the mobile default, preserve the richer desktop/tablet behavior, and make it a documented eSiasa UI rule: full-record mobile flows should navigate to stable routes rather than open dialogs or inline detail.

- **Confidence:** Medium-high. The route behavior, direct detail loading, overflow fix, and validation are supported [E2-E6]. Confidence is not high because field acceptance and audit telemetry are not in the ledger.
- **What would change this:** Evidence that mobile operators abandon the route-backed flow more often than dialog/inline detail, or that the route creates unresolved authorization/audit gaps.
- **Unresolved dissent:** Bhagwati's missing-stakeholder concern remains: field users and county operators were not represented in the ledger.

## 7. Decision (human)

<Left blank. The Sovereign Conclave advises; you decide, and you own the call.>
