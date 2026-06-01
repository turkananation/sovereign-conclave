# Sovereign Conclave

![Sovereign Conclave banner](docs/assets/sovereign-conclave-banner.svg)

**Sovereign Conclave is an evidence-grounded deliberation protocol for hard decisions.** It convenes a small set of deliberately opposed seats, forces every factual claim back to a frozen [Evidence Ledger](docs/EVIDENCE_LEDGER.md), preserves dissent, and writes a decision record that advises the human without authorizing action.

It is built for decisions where a fluent single answer is not enough: architecture calls, institutional strategy, civic-risk review, emergency preparedness, red-team war-gaming, governance tradeoffs, and high-consequence product or policy choices.

## What It Is

Sovereign Conclave is a portable skill package for Claude Code, Codex, and Antigravity.

At its core, it gives an assistant a repeatable protocol:

1. Freeze the [Evidence Ledger](docs/EVIDENCE_LEDGER.md).
2. Frame the actual decision and options.
3. Convene a small quorum from a larger seat library.
4. Run blind first-round analysis to prevent herding.
5. Cross-examine the claims.
6. Let Marshall verify support against the ledger.
7. Produce a written verdict with confidence, dissent, and what would change the recommendation.

The project currently includes:

- 33 active seats spanning generals, sovereigns, Justices, danger lenses, and Inner Sanctum thinkers.
- 24 convening profiles across domains: code, strategy, geopolitics, space, cryptography, economics, leadership, war-gaming, and more.
- 22 polarity pairs.
- Structural Justice checks for evidence, rights, access, values, and dignity.
- A multi-target installer for Claude Code, Codex, and Antigravity.
- A machine-readable roster/profile config.
- A local verdict-scaffold runner.
- CI and repository validation scripts.
- Curated demo verdicts.

## What It Can Do

Sovereign Conclave is not a coding tool. It is a **deliberation protocol for any high-stakes decision** where a fluent single answer is not enough and where the cost of being wrong is real.

### Technology & Engineering

- Pressure-test a technical architecture decision (microservices vs. monolith, cloud vs. on-prem).
- Stress-test a cryptographic protocol design for dual-use risk, formal correctness, and rights implications.
- Review an AI system deployment: capability, consequence, audit trail, proportionality.
- Evaluate a mathematics-heavy algorithm for correctness assumptions, dual-use potential, and access equity.
- War-game a software launch plan before it ships.

### Geopolitics & International Relations

- Deliberate a great-power competition strategy with seats spanning offensive action, asymmetric resistance, institutional consolidation, and access-and-standing checks.
- Assess a sanctions regime for proportionality, efficacy, and unintended harm.
- Stress-test a treaty negotiation: what does the adversary exploit, and who is unheard?
- Examine a border dispute through military, legal, indigenous, and ecological lenses simultaneously.

### Space & Frontier Science

- Evaluate a space-resource extraction policy for dual-use risk, access equity, and long-run consequence.
- Deliberate on a planetary-defense response where capability and consequence are inseparable.
- Assess a space-nation governance framework: who gets access, who sets the rules, who is excluded?
- Review a moonshot R&D programme for formal model soundness, oversight architecture, and dignity.

### Economics & Globalisation

- Deliberate on a trade agreement's winners and losers across growth, equity, ecology, and legitimacy.
- Stress-test an economic development strategy: what works at scale vs. what sounds principled?
- Examine a central-bank intervention through game-theoretic, reconciliation, and standing-check lenses.
- Review an international debt restructuring for repair, access, and self-determination.

### Leadership & Institutions

- War-game a succession plan: does the institution outlast the founder?
- Stress-test a board's governance model for coercive drift, dignity failure, and missing stakeholders.
- Deliberate on a cultural transformation programme: does it empower the governed or consolidate authority?
- Review an organisational crisis response for strategic endurance, public-trust, and lawful process.

### Crisis, Security & Preparedness

- Evaluate a pandemic-preparedness plan across access, rights, whole-of-government readiness, and community trust.
- Review an emergency-powers framework for lawful limits, sunset discipline, and oversight.
- War-game a continuity-of-government scenario with full military, executive, legal, and civic lenses.
- Assess an intelligence programme for oversight debt, civil liberties, and institutional legitimacy.

### Environment & Land

- Deliberate on a land-use policy across ecological stewardship, development efficiency, colonial history, and legal proportionality.
- Stress-test a carbon-trading scheme for equity, access, and repair obligations.
- Review a conservation programme that affects indigenous communities for self-determination, standing, and dignity.

### Justice, Rights & Transitional Processes

- Evaluate a truth-and-reconciliation design for repair, memory, coexistence, and constitutional values.
- Review a decolonisation policy for land, restitution, self-determination, and whether grievance is genuinely addressed.
- Stress-test a rights framework for proportionality, access, dignity, and constitutional survivability.

### Mathematics, Cryptography & Formal Systems

- Apply first-principles and game-theoretic analysis to a cryptographic protocol or formal verification claim.
- Stress-test an algorithmic decision system for dual-use risk, rights proportionality, and audit accountability.
- Deliberate on a post-quantum migration plan: formal correctness, access equity, and lawful process.

The Sovereign Conclave does **not** make autonomous decisions. It does **not** deploy, spend, push, execute, or authorize irreversible action. It advises; the human decides.

## Why It Is Different

Most "multi-agent council" patterns fail by becoming theater: many voices, one model, little grounding, no record of what was actually supported.

Sovereign Conclave is built around a stricter spine:

- **Evidence first:** no load-bearing factual claim without an `E#` citation.
- **Blind Round 1:** seats argue independently before seeing one another.
- **Forced dissent:** early convergence triggers a counterfactual pass.
- **Marshall always verifies:** unsupported decisive claims downgrade the verdict.
- **Seats are lenses, not capabilities:** a persona name does not grant expertise.
- **6-seat default, 33-seat maximum:** focused by default; scalable to full civilizational breadth.
- **Advice only:** output is a recommendation to the human, never an action order.

## Quick Start

Validate the checkout:

```bash
python3 scripts/validate_repo.py
bash -n install.sh
./install.sh --target all --dry-run
```

Install for your tool:

```bash
./install.sh                          # Claude Code, default target
./install.sh --target codex           # Codex
./install.sh --target antigravity     # Antigravity
./install.sh --target all --dry-run   # preview every target
./install.sh --uninstall --target all # remove from every target
```

Restart the target tool after installation.

## The 33 Seats — Full Roster with Rationale

Every seat is a **lens**, not a skill. A persona name does not grant capability; it fixes a deliberative stance. Full display names appear in verdicts and output.

| Full Name | Seat ID | Tier | Lens | Why This Persona |
| --- | --- | --- | --- | --- |
| **Georgy Zhukov** | `conclave-zhukov` | General | Decisive force, initiative, operational reach | Commanded the largest land battles in history (Kursk, Berlin); the definitive lens for when to mass forces, seize initiative, and accept high-risk decisive action. |
| **George Washington** | `conclave-washington` | General | Strategic endurance; preserve the force and legitimacy | Held together an outmatched revolutionary army for 8 years by refusing decisive risk; the lens for institutional survival over battlefield glory. |
| **John J. Pershing** | `conclave-pershing` | General | Organized capability, logistics, training, unity of command | Built the AEF from nothing in WWI and refused to subordinate US forces under a failed command; the lens for readiness, logistics, and committed mass. |
| **Võ Nguyên Giáp** | `conclave-giap` | General | Asymmetric protraction; terrain, will, political clock | Defeated France then the USA through protracted guerrilla war; the definitive lens for fighting from material weakness by making political will the decisive weapon. |
| **Yi Sun-sin** | `conclave-yi-sun-shin` | General | Prepared defense, discipline, favorable terrain | Won decisive naval battles against vastly superior Japanese forces through discipline and terrain mastery; the lens for winning by making your own defeat structurally impossible. |
| **Stanley McChrystal** | `conclave-mcchrystal` | General | Networked mission command, decentralized execution | Transformed a rigid SOF hierarchy into a distributed "team of teams"; the lens for shared consciousness, mission command, and organisational adaptability at speed. |
| **Lee Kuan Yew** | `conclave-lee-kuan-yew` | Sovereign | What works at scale, resource discipline | Took Singapore from third-world city-state to first-world economy in one generation through disciplined pragmatism; the lens for what actually works versus what merely sounds principled. |
| **Augustus Caesar** | `conclave-augustus` | Sovereign | Durable institutions, legitimacy, consolidation | Converted a violent dying republic into a 400-year empire by engineering legitimacy rather than relying on force; the lens for making power outlast the founder. |
| **Suleiman the Magnificent** | `conclave-suleiman` | Sovereign | Codified law, uniform administration, cohesion | Governed a vast multi-ethnic empire through law applied consistently across difference; the lens for binding diverse domains through rules rather than pure coercion. |
| **Queen Elizabeth I** | `conclave-elizabeth` | Sovereign | Optionality, ambiguity, parsimony, balancing rivals | Survived decades of existential threat through strategic ambiguity and rival-balancing, spending nothing she did not have to; the lens for preserving optionality and committing only when forced. |
| **Sejong the Great** | `conclave-sejong` | Sovereign | Capability of the governed; accessible systems | Created Hangul to make literacy available to ordinary Koreans rather than just the court; the lens for governance that serves those governed, not only those who govern. |
| **Nelson Mandela** | `conclave-mandela` | Sovereign | Reconciliation, legitimacy, durable peace | Chose inclusion over retribution after 27 years in prison, leading the first post-apartheid government; the lens for durable settlements that bring adversaries inside rather than punishing them out. |
| **Toussaint Louverture** | `conclave-toussaint` | Sovereign | Liberation, self-determination, sovereignty from below | Led the only successful large-scale slave revolution in history and founded Haiti; the lens for refusing the master's bargain and building sovereignty from the dispossessed. |
| **Barack Obama** | `conclave-obama` | Sovereign | Public-trust preparedness and coalition governance | Built whole-of-government public health and pandemic preparedness infrastructure; the lens that preparedness only works when the public trusts the messenger. |
| **George W. Bush** | `conclave-bush` | Sovereign | Continuity, biodefense readiness, hardened crisis governance | Architect of post-9/11 continuity-of-government infrastructure and PEPFAR; the lens for hardening institutions before the emergency arrives. |
| **Dick Cheney** | `conclave-cheney` | Emergency Executive | Concentrated command authority under worst-case threat | Architect of expanded post-9/11 executive power doctrine; the lens for the case that divided authority and legal ambiguity can destroy the state before process catches up in existential emergencies. |
| **Michael Hayden** | `conclave-hayden` | Intelligence | Hidden threats, collection discipline, secrecy with oversight debt | Led NSA mass surveillance programs (STELLARWIND) and CIA programs; the lens that hidden threats require hidden tools, but secrecy accumulates oversight debt that must be named. |
| **Authoritarian Control** | `conclave-authoritarian` | Danger Lens | Coercive control, fear, surveillance, patronage, false stability | An unnamed coercive-authority danger lens; forces the conclave to name the authoritarian temptation before it hides inside a "stability" or "efficiency" argument. |
| **David Addington** | `conclave-addington` | Law | Legal process, accountability channels, protected records | VP Cheney's counsel and chief of staff, expert in executive branch legal architecture; the lens that decisions must survive lawful process or they will not remain institutionally legitimate. |
| **Wangari Maathai** | `conclave-maathai` | Civic Ecology | Grassroots stewardship, land, community legitimacy | Founded Kenya's Green Belt Movement linking environmental degradation to governance failure; Nobel Peace Prize 2004; the lens for sustainability that requires community legitimacy, not only technical solutions. |
| **Colonial Administrator** | `conclave-colonial-administrator` | Danger Lens | Extractive administration, indirect rule, classification, order without belonging | An unnamed extractive-colonial danger lens; forces the conclave to name classification, indirect rule, extraction, and order-without-belonging before they masquerade as neutral administration. |
| **Mau Mau** | `conclave-mau-mau` | Liberation | Land, dignity, dispossession, closed lawful channels, resistance | The Kenya Land and Freedom Army lens; voices what happens when land dispossession and dignity denial are left unaddressed until closed lawful channels leave only resistance. |
| **Marshall (Verifier)** | `conclave-marshall` | Justice (always) | Evidence-grounding and directive check | The conclave's structural guardrail — not an advocate. Every decisive claim is tagged Supported / Unsupported / Contested against the Evidence Ledger. Always convened; cannot be removed. |
| **Baroness Brenda Hale** | `conclave-lady-hale` | Justice | Proportionality and rights check | First female President of the UK Supreme Court; her structural check is that means must be proportionate to ends and rights bind even useful or popular decisions. |
| **Justice P.N. Bhagwati** | `conclave-bhagwati` | Justice | Access, standing, and missing-stakeholder check | Chief Justice of India who pioneered Public Interest Litigation, opening courts to those who could not afford them; his check is who has standing and who is being decided for without their voice. |
| **Arthur Chaskalson** | `conclave-chaskalson` | Justice | Constitutional values and dignity check | Founding President of South Africa's Constitutional Court and architect of the post-apartheid rights framework; his check is whether a decision violates first-order dignity even if efficient or popular. |
| **Justice Robert Jackson** | `conclave-jackson` | Justice | Emergency authority, institutional role, oversight, and sunset check | US Supreme Court Justice and chief Nuremberg prosecutor; his check is whether claimed emergency power has authority, lawful limits, oversight, and a path back to normal governance. |
| **Justice Albie Sachs** | `conclave-sachs` | Justice | Repair, memory, remedy, restoration, and transitional legitimacy check | South African Constitutional Court Justice, bomb-attack survivor who chose reconciliation over retribution; his check is whether past harm is genuinely repaired or merely managed. |
| **Richard Feynman** | `conclave-feynman` | Inner Sanctum | First principles, refuses unexplained complexity | Nobel physicist who exposed the Challenger O-ring failure with a glass of ice water; the lens for rebuilding a problem from the ground up and refusing any complexity that cannot be explained simply. |
| **Marcus Aurelius** | `conclave-aurelius` | Inner Sanctum | Downside containment, restraint, moral clarity | Philosopher-emperor who governed Rome while privately recording Meditations on what is and is not within our control; the lens for downside containment and moral clarity under pressure. |
| **John von Neumann** | `conclave-von-neumann` | Inner Sanctum | Formal modeling, game theory, expected value | Co-inventor of game theory and foundational computer architecture; the lens for reducing a decision to formal models, payoffs, equilibria, and minimax pressure before intuition takes over. |
| **J. Robert Oppenheimer** | `conclave-oppenheimer` | Inner Sanctum | Capability, consequence, dual-use control | Scientific director of the Manhattan Project, later stripped of his security clearance; the lens that powerful tools carry ethical weight the deployer cannot disclaim after deployment. |
| **Sun Tzu (孫子)** | `conclave-sun-tzu` | Inner Sanctum | Win before fighting; positioning and deception | Author of *The Art of War* (~500 BCE); the lens for shaping conditions before direct conflict — know adversary and self, control terrain, and never fight a battle you have not already won. |

## Use In An Assistant

Use `/conclave` where slash commands are supported:

```text
/conclave Should we move the notifications service off Cloud Run?
/conclave --profile architecture Monorepo or polyrepo for the new modules?
/conclave --profile war-game Pressure-test our launch plan for next quarter.
/conclave --profile war-cabinet Evaluate the tactical options for the border situation.
/conclave --profile geopolitics How should we respond to the rival bloc’s regional expansion?
/conclave --profile economic-thinktank Is this trade agreement good for development equity?
/conclave --profile space-exploration Deliberate the asteroid-mining rights framework.
/conclave --profile formal-science Stress-test this post-quantum cryptography migration plan.
/conclave --profile pandemic-preparedness County outbreak readiness and communications plan?
/conclave --profile leadership How should the organisation navigate this succession crisis?
/conclave --profile esiasa-civic-stress Stress-test the new county intelligence dossier flow.
/conclave --profile oppression-audit Does this crisis plan create coercive drift?
/conclave --profile decolonization Are we missing land, dignity, or repair obligations?
/conclave --profile half-conclave A cross-domain decision that touches strategy, rights, and ecology.
/conclave --profile full-conclave Civilizational-scale question: should humanity colonise Mars?
/conclave --members feynman,lee-kuan-yew,aurelius Is the caching design sound?
```

Paste or attach the real artifacts before Round 1. They become the [Evidence Ledger](docs/EVIDENCE_LEDGER.md), and Marshall flags claims that are unsupported by it.

## Local Runner

By default the local runner is deterministic: it selects seats from `configs/conclave-roster.json` and creates a verdict scaffold without calling any model provider or synthesizing claims. Real provider-backed deliberation is available opt-in via `--provider-run` (off by default, env-only keys; see below).

```bash
bin/conclave --list-profiles
bin/conclave --profile pandemic-preparedness --dry-run "County outbreak readiness plan"
bin/conclave --profile architecture --stdout "Move notifications off Cloud Run?"
bin/conclave --profile risk --evidence-file README.md --evidence-note "Rollback plan is pending owner approval." --stdout "Can this release go out?"
bin/conclave --profile pandemic-preparedness --ledger-file demos/evidence-ledgers/pandemic-preparedness-county-response.json --stdout "Approve the county outbreak-response plan?"
bin/conclave --validate-ledger demos/evidence-ledgers/pandemic-preparedness-county-response.json
bin/conclave --profile risk --evidence-file README.md --write-ledger ledgers/release-risk.json --stdout "Can this release go out?"
```

Generated local verdicts go to `verdicts/`, and private machine-readable ledgers go to `ledgers/`. Both are ignored by git except for `.gitkeep` because they may contain sensitive evidence.

The runner is deterministic and offline by default. For real provider-backed deliberation, opt in with `bin/conclave --provider-run` — off by default, credentials from the environment only, with a graceful fallback to the scaffold. See [docs/RUNNER.md](docs/RUNNER.md).

## Profiles

| Profile | Seats (besides Marshall) | Use For |
| --- | --- | --- |
| `architecture` | Feynman + Lee Kuan Yew + von Neumann + Oppenheimer + Aurelius + Addington | Code, system design, platform, or irreversible technical capability calls |
| `strategy` | Zhukov + Washington + Sun Tzu + Aurelius + Elizabeth + von Neumann | Competitive, directional, timing, and commitment decisions |
| `risk` | Aurelius + Yi Sun-sin + Oppenheimer + Lady Hale + Feynman + Chaskalson | Downside, safety, security, rights, and failure-mode review |
| `institutional` | Augustus + Mandela + Lee Kuan Yew + Bhagwati + Sejong + Chaskalson | Governance, legitimacy, operating model, and stakeholder decisions |
| `policy` | Suleiman + Elizabeth + Sejong + Chaskalson + Bhagwati + Addington | Rules, access, administration, public-facing systems, and value constraints |
| `liberation` | Toussaint + Augustus + Mandela + Lady Hale + Mau Mau + Sachs | Imposed-order, self-determination, independence, and rights-heavy decisions |
| `war-game` | Sun Tzu + Giáp + Zhukov + McChrystal + Washington + one Justice | Adversarial stress-test where the adversary is free to win |
| `war-cabinet` | Zhukov + McChrystal + Cheney + Bush + Hayden + Jackson + Addington | Crisis command: military options, executive authority, intelligence, lawful limits |
| `economic-thinktank` | Lee Kuan Yew + Sejong + von Neumann + Mandela + Bhagwati + Maathai | Economic policy, development, growth vs. equity, sustainable governance |
| `geopolitics` | Sun Tzu + Augustus + Elizabeth + Suleiman + Giáp + Washington + Bhagwati | International relations, great-power competition, alliance strategy, diplomacy |
| `space-exploration` | Oppenheimer + Feynman + von Neumann + Aurelius + Bhagwati + Chaskalson + Sejong | Space policy, frontier technology ethics, resource extraction, access equity |
| `formal-science` | Feynman + von Neumann + Oppenheimer + Aurelius + Lady Hale + Addington | Mathematics, cryptography, formal verification, algorithm design, dual-use science |
| `globalisation` | Lee Kuan Yew + Augustus + Mandela + Toussaint + Sejong + Maathai + Bhagwati | Globalisation tradeoffs, cross-border governance, inequality, cultural self-determination |
| `leadership` | Washington + Mandela + Sejong + McChrystal + Aurelius + Bhagwati | Leadership, succession, institutional character, leading through adversity |
| `esiasa-civic-stress` | McChrystal + Hayden + Maathai + Addington + Bhagwati + Sejong | County/civic-stress, admin intelligence, route-backed dossiers, resilience work |
| `continuity` | Bush + Cheney + Obama + Hayden + Chaskalson + Jackson | Continuity of government, emergency authority, succession, crisis governance |
| `pandemic-preparedness` | Obama + Bush + Sejong + Bhagwati + Lady Hale + Maathai | Public-health readiness, civic compliance, access, rights, whole-of-government response |
| `intelligence-oversight` | Hayden + Addington + Lady Hale + Chaskalson + Obama + Jackson | Intelligence products, surveillance, lawful process, civil liberties, trust |
| `environmental-governance` | Maathai + Sejong + Mandela + Lee Kuan Yew + Lady Hale + Sachs | Land, environment, resilience, public participation, stewardship |
| `oppression-audit` | Authoritarian Control + Hayden + Cheney + Jackson + Lady Hale + Chaskalson | Detecting coercion, surveillance drift, rights violations, dignity failure |
| `decolonization` | Colonial Administrator + Mau Mau + Toussaint + Maathai + Bhagwati + Sachs | Land, dispossession, colonial patterns, restitution, self-determination, repair |
| `emergency-powers` | Cheney + Bush + Jackson + Lady Hale + Addington + Chaskalson | Crisis authority, continuity, lawful limits, oversight, sunset discipline |
| `half-conclave` | 17 balanced seats (see roster.md) | Cross-domain decisions needing broad coverage without full 33 |
| `full-conclave` | All 32 advocate seats | Civilizational-scale or genuinely irreversible decisions |

Marshall is convened in every run even when not named.

## Example Verdicts

Curated examples live under [demos/verdicts/](demos/verdicts/):

- [architecture-notifications-platform-split.md](demos/verdicts/architecture-notifications-platform-split.md)
- [war-game-launch-plan.md](demos/verdicts/war-game-launch-plan.md)
- [esiasa-civic-stress-route-backed-dossier.md](demos/verdicts/esiasa-civic-stress-route-backed-dossier.md)
- [pandemic-preparedness-county-response.md](demos/verdicts/pandemic-preparedness-county-response.md)
- [self-war-game-repo-readiness.md](demos/verdicts/self-war-game-repo-readiness.md)

They show the expected standard: clear decision framing, frozen evidence, real disagreement, Marshall verification, confidence, unresolved dissent, and advice-only recommendation language. [docs/GOOD_VS_BAD_VERDICTS.md](docs/GOOD_VS_BAD_VERDICTS.md) contrasts a grounded verdict with a fluent, ungrounded one on the same decision.

The self-war-game example is intentionally historical: it captures the repo inspecting its own pre-hardening state, surfacing a stale provider-backed transcript test expectation and generated-roster drift before those issues were fixed. The full public example set for that run is:

- [demos/prompts/self-war-game-repo-readiness.md](demos/prompts/self-war-game-repo-readiness.md)
- [demos/evidence-ledgers/self-war-game-repo-readiness.json](demos/evidence-ledgers/self-war-game-repo-readiness.json)
- [demos/verdicts/self-war-game-repo-readiness.md](demos/verdicts/self-war-game-repo-readiness.md)

## Repository Map

| Path | Purpose |
| --- | --- |
| [SKILL.md](SKILL.md) | The `/conclave` protocol and assistant-facing command definition |
| [directives.md](directives.md) | Standing rules: evidence, assumptions, dissent, advice-only, no-secret defaults |
| [agents/conclave-*.md](agents/) | Seat definitions |
| [agents/_TEMPLATE.md](agents/_TEMPLATE.md) | Template for future seats |
| [roster.md](roster.md) | Human-readable roster, polarity pairs, and profiles |
| [configs/conclave-roster.json](configs/conclave-roster.json) | Machine-readable seats, profiles, polarity pairs, and quorum rules |
| [configs/provider-model-slots.example.yaml](configs/provider-model-slots.example.yaml) | Optional provider/model slot example |
| [schemas/evidence-ledger.schema.json](schemas/evidence-ledger.schema.json) | Machine-readable Evidence Ledger schema |
| [scripts/generate_roster.py](scripts/generate_roster.py) | Generates `roster.md` from the machine-readable config |
| [scripts/validate_repo.py](scripts/validate_repo.py) | Repository invariant validator |
| [scripts/evidence_ledger.py](scripts/evidence_ledger.py) | Dependency-free Evidence Ledger JSON validation helpers |
| [tests/](tests/) | Unit tests for the Evidence Ledger validator and the runner |
| [bin/conclave](bin/conclave) | Local verdict-scaffold runner |
| [demos/verdict-template.md](demos/verdict-template.md) | Blank verdict format |
| [demos/evidence-ledger-template.md](demos/evidence-ledger-template.md) | Standalone Evidence Ledger preparation template |
| [demos/evidence-ledgers/](demos/evidence-ledgers/) | Public machine-readable demo ledgers |
| [demos/prompts/](demos/prompts/) | Public prompt examples used to generate tracked demos |
| [demos/verdicts/](demos/verdicts/) | Curated example verdicts |
| [ledgers/](ledgers/) | Private machine-readable ledgers, git-ignored except `.gitkeep` |
| [docs/](docs/) | Quickstart, concepts, runner docs, roadmap, progress tracker |
| [.github/workflows/ci.yml](.github/workflows/ci.yml) | CI validation workflow |

## Documentation

- [docs/README.md](docs/README.md) - documentation index.
- [docs/QUICKSTART.md](docs/QUICKSTART.md) - shortest path to install and run.
- [docs/CONCEPTS.md](docs/CONCEPTS.md) - seats, Evidence Ledger, Marshall, Justices, profiles, runner.
- [docs/EVIDENCE_LEDGER.md](docs/EVIDENCE_LEDGER.md) - the Evidence Ledger contract, table shape, citation rules, source quality, redaction guidance, and runner usage.
- [docs/RUNNER.md](docs/RUNNER.md) - local runner behavior and limitations.
- [docs/SEAT_EXPANSION_RATIONALE.md](docs/SEAT_EXPANSION_RATIONALE.md) - why the library expands to 33 seats and how the added danger, grievance, and Justice lenses are bounded.
- [docs/FEATURE_ROADMAP.md](docs/FEATURE_ROADMAP.md) - planned work and effort.
- [docs/PROGRESS_TRACKER.md](docs/PROGRESS_TRACKER.md) - release state and milestones.
- [CHANGELOG.md](CHANGELOG.md) - release history beginning at `0.1.0`.
- [SECURITY.md](SECURITY.md) - sensitive-data and disclosure guidance.
- [CONTRIBUTING.md](CONTRIBUTING.md) - contribution rules and seat proposal standards.

## License

Sovereign Conclave is released under the BSD 3-Clause License. See [LICENSE](LICENSE).
