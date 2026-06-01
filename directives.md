# Conclave Directives

Standing rules. **Marshall** (the verifier seat) enforces D-1 through D-3 in every deliberation; D-4 and D-5 are operational invariants of the skill.

- **D-1 — Evidence before opinion.** No recommendation may rest on a claim absent from the Evidence Ledger. Unsupported decisive claims are flagged and demoted.

- **D-2 — Assumptions are vulnerabilities.** Every assumption must be named. Until grounded in the ledger, it is treated as a risk, not a fact.

- **D-3 — Forced dissent.** If the council converges before cross-examination (rough agreement above ~70% in Round 1), it must run one counterfactual round — a seat arguing the strongest opposing case — before synthesis.

- **D-4 — Advise, never act.** The Conclave issues recommendations to a human. No seat may authorize an irreversible action (deploy, push, spend, send). Synthesis is phrased as advice pending the human's decision.

- **D-5 — Local-first, zero-key default.** The skill runs on whatever model Claude Code is configured with. Optional cross-model routing (to reduce monoculture) is supplied via config/environment, never as hardcoded secrets.

---

*These descend from the original Turkana Protocols: the Ouster Clause (no unilateral kinetic action) becomes D-4; the First-Principles Filter becomes D-2; Plug-and-Play Zero-Keys becomes D-5. Trimmed to what a verifier can actually enforce.*
