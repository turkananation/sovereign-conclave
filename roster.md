# The Conclave Roster

The Conclave is a **library** of seats, not a standing assembly. You convene a small **quorum** per decision: 3-8 seats plus Marshall. The library can be large; the meeting stays small. A seat earns inclusion only by arguing a stance no current seat covers, or by enforcing a structural check no other Justice owns.

Marshall is convened in every deliberation. The other Justices are optional structural checks: they hold no opinion on which option should win.

## Active seats (agent files written)

| Seat | Tier | Lens | Model |
| --- | --- | --- | --- |
| `conclave-zhukov` | General | Decisive force, initiative, operational reach | sonnet |
| `conclave-washington` | General | Strategic endurance; preserve the force and legitimacy | sonnet |
| `conclave-pershing` | General | Organized capability, logistics, training, unity of command | sonnet |
| `conclave-giap` | General | Asymmetric protraction; terrain, will, political clock | sonnet |
| `conclave-yi-sun-shin` | General | Prepared defense, discipline, favorable terrain | sonnet |
| `conclave-mcchrystal` | General | Networked mission command and decentralized execution | sonnet |
| `conclave-lee-kuan-yew` | Sovereign | What works at scale, resource discipline | sonnet |
| `conclave-augustus` | Sovereign | Durable institutions, legitimacy, consolidation | opus |
| `conclave-suleiman` | Sovereign | Codified law, uniform administration, cohesion | sonnet |
| `conclave-elizabeth` | Sovereign | Optionality, ambiguity, parsimony, balancing rivals | opus |
| `conclave-sejong` | Sovereign | Capability of the governed; accessible systems | sonnet |
| `conclave-mandela` | Sovereign | Reconciliation, legitimacy, durable peace | opus |
| `conclave-toussaint` | Sovereign | Liberation, self-determination, sovereignty from below | sonnet |
| `conclave-obama` | Sovereign | Public-trust preparedness and coalition governance | opus |
| `conclave-bush` | Sovereign | Continuity, biodefense readiness, hardened crisis governance | opus |
| `conclave-cheney` | Emergency Executive | Concentrated command authority under worst-case threat | opus |
| `conclave-hayden` | Intelligence | Hidden threats, collection discipline, secrecy with oversight debt | opus |
| `conclave-authoritarian` | Danger Lens | Coercive control, fear, surveillance, patronage, and false stability | opus |
| `conclave-atkinson` | Law | Legal process, accountability channels, protected records | opus |
| `conclave-maathai` | Civic Ecology | Grassroots stewardship, land, community legitimacy | sonnet |
| `conclave-colonial-administrator` | Danger Lens | Extractive administration, indirect rule, classification, and order without belonging | opus |
| `conclave-mau-mau` | Liberation | Land, dignity, dispossession, closed lawful channels, and resistance pressure | sonnet |
| `conclave-marshall` | Justice (always) | Evidence-grounding and directive check | opus |
| `conclave-lady-hale` | Justice | Proportionality and rights check | opus |
| `conclave-bhagwati` | Justice | Access, standing, and missing-stakeholder check | opus |
| `conclave-chaskalson` | Justice | Constitutional values and dignity check | opus |
| `conclave-jackson` | Justice | Emergency authority, institutional role, oversight, and sunset check | opus |
| `conclave-sachs` | Justice | Repair, memory, remedy, restoration, and transitional legitimacy check | opus |
| `conclave-feynman` | Inner Sanctum | First principles, refuses unexplained complexity | sonnet |
| `conclave-aurelius` | Inner Sanctum | Downside containment, restraint, moral clarity | opus |
| `conclave-von-neumann` | Inner Sanctum | Formal modeling, game theory, expected value | opus |
| `conclave-oppenheimer` | Inner Sanctum | Capability, consequence, dual-use control | opus |
| `conclave-sun-tzu` | Inner Sanctum | Win before fighting; positioning and deception | opus |

## Library status

The 33-seat library is written. It includes the core pantheon, eSiasa-oriented extension seats, danger lenses for ugly governance logics, and additional Justice checks. Add a new seat the same way only when it brings a stance or structural check no existing seat covers:

1. Copy `agents/_TEMPLATE.md`.
2. Give the seat one clear lens, an owned bias, a "You are NOT" boundary, and a polarity partner.
3. Keep the seat as a lens, never a claim that the model gained a new capability.

Two seats that agree are one seat and a cost.

## Polarity pairs

These are the canonical contrasts. Use them to build small quorums with real disagreement.

| Pair | Contrast |
| --- | --- |
| Zhukov ⟷ Aurelius | Decisive action vs. restraint and downside containment |
| Washington ⟷ Zhukov | Strategic endurance vs. decisive audacity |
| Giáp ⟷ Pershing | Asymmetric improvisation vs. industrial mass |
| Suleiman ⟷ Elizabeth | Codify and commit vs. hedge and preserve optionality |
| Mandela ⟷ Lee Kuan Yew | Reconciliation and legitimacy vs. efficient technocratic order |
| Augustus ⟷ Toussaint | Consolidate the center vs. liberate the periphery |
| Sejong ⟷ Augustus | Empower the many vs. consolidate authority |
| von Neumann ⟷ Feynman | Formal model vs. bottom-up mechanism |
| Oppenheimer ⟷ Zhukov | Reckon with consequence vs. deploy capability |
| Sun Tzu ⟷ Aurelius | External advantage vs. internal character |
| Lee Kuan Yew ⟷ Feynman | What works in practice vs. what is explainable in principle |
| McChrystal ⟷ Pershing | Networked mission command vs. formal mass and readiness |
| Hayden ⟷ Lady Hale | Security secrecy vs. proportionality and rights |
| Obama ⟷ Bush | Public-trust preparedness vs. hardened continuity |
| Atkinson ⟷ Cheney | Lawful accountability channels vs. emergency executive power |
| Maathai ⟷ Lee Kuan Yew | Grassroots ecological legitimacy vs. technocratic developmental efficiency |
| Authoritarian Control ⟷ Chaskalson | Coercive control vs. constitutional values and dignity |
| Colonial Administrator ⟷ Mau Mau | Extractive indirect order vs. anti-colonial land and dignity grievance |
| Jackson ⟷ Cheney | Emergency authority limits vs. emergency executive concentration |
| Sachs ⟷ Authoritarian Control | Repair and transitional legitimacy vs. coercive control |
| Colonial Administrator ⟷ Maathai | Extractive administration vs. ecological civic stewardship |

## Convening profiles

Marshall is always in. Pick one profile, or name members directly with `--members`. Keep quorums to 3-8 seats plus Marshall.

| Profile | Seats besides Marshall | Use for |
| --- | --- | --- |
| `architecture` | Feynman + Lee Kuan Yew + von Neumann + Oppenheimer | Code, system design, platform, or irreversible technical capability calls |
| `strategy` | Zhukov + Washington + Sun Tzu + Aurelius | Competitive, directional, timing, and commitment decisions |
| `risk` | Aurelius + Yi Sun-shin + Oppenheimer + Lady Hale | Downside, safety, security, rights, and failure-mode review |
| `institutional` | Augustus + Mandela + Lee Kuan Yew + Bhagwati | Governance, legitimacy, operating model, and stakeholder decisions |
| `policy` | Suleiman + Elizabeth + Sejong + Chaskalson | Rules, access, administration, public-facing systems, and value constraints |
| `liberation` | Toussaint + Augustus + Mandela + Lady Hale | Imposed-order, self-determination, independence, and rights-heavy decisions |
| `war-game` | Blue cell + Sun Tzu + Giáp + one Justice | Adversarial stress-test where the adversary is free to win |
| `esiasa-civic-stress` | McChrystal + Hayden + Maathai + Atkinson + Bhagwati | County/civic-stress, admin intelligence, route-backed dossiers, and legitimacy-heavy resilience work |
| `continuity` | Bush + Cheney + Obama + Hayden + Chaskalson | Continuity of government, emergency authority, succession, and crisis governance |
| `pandemic-preparedness` | Obama + Bush + Sejong + Bhagwati + Lady Hale | Public-health readiness, civic compliance, access, rights, and whole-of-government response |
| `intelligence-oversight` | Hayden + Atkinson + Lady Hale + Chaskalson + Obama | Intelligence products, surveillance, lawful process, civil liberties, and trust |
| `environmental-governance` | Maathai + Sejong + Mandela + Lee Kuan Yew + Lady Hale | Land, environment, county resilience, public participation, and implementable stewardship |
| `oppression-audit` | Authoritarian Control + Hayden + Cheney + Jackson + Lady Hale + Chaskalson | Detecting coercion, surveillance, emergency drift, rights violations, and dignity failure |
| `decolonization` | Colonial Administrator + Mau Mau + Toussaint + Maathai + Bhagwati + Sachs | Land, dispossession, colonial patterns, restitution, self-determination, and repair |
| `emergency-powers` | Cheney + Bush + Jackson + Lady Hale + Atkinson + Chaskalson | Crisis authority, continuity, lawful limits, oversight, records, and sunset discipline |

### `war-game` cells

- **Blue cell:** the seat or seats defending the current plan. Pick 1-3 based on the plan: Zhukov for decisive execution, Washington for preservation, Pershing for readiness, Yi Sun-shin for prepared defense, Lee Kuan Yew for operational viability.
- **Red cell:** Sun Tzu + Giáp. They are the adversary, free to win; they exploit deception, terrain, time, will, and asymmetric pressure.
- **White cell:** Marshall + one Justice. Marshall adjudicates grounding and directive compliance. Pick Lady Hale for proportionality/rights, Bhagwati for unheard stakeholders, or Chaskalson for foundational values and dignity. White may inject events and judge what the ledger supports.
