# The Sovereign Conclave Roster

The Sovereign Conclave is a **library** of seats, not a standing assembly. You convene a small **quorum** per decision: 3-8 seats plus Marshall. The library can be large; the meeting stays small. A seat earns inclusion only by arguing a stance no current seat covers, or by enforcing a structural check no other Justice owns.

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
| `conclave-addington` | Law | Legal process, accountability channels, protected records | opus |
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
| Georgy Zhukov ⟷ Marcus Aurelius | Decisive action vs. restraint and downside containment |
| George Washington ⟷ Georgy Zhukov | Strategic endurance vs. decisive audacity |
| Võ Nguyên Giáp ⟷ John J. Pershing | Asymmetric improvisation vs. industrial mass |
| Suleiman the Magnificent ⟷ Queen Elizabeth I | Codify and commit vs. hedge and preserve optionality |
| Nelson Mandela ⟷ Lee Kuan Yew | Reconciliation and legitimacy vs. efficient technocratic order |
| Augustus Caesar ⟷ Toussaint Louverture | Consolidate the center vs. liberate the periphery |
| Sejong the Great ⟷ Augustus Caesar | Empower the many vs. consolidate authority |
| John von Neumann ⟷ Richard Feynman | Formal model vs. bottom-up mechanism |
| J. Robert Oppenheimer ⟷ Georgy Zhukov | Reckon with consequence vs. deploy capability |
| Sun Tzu (孫子) ⟷ Marcus Aurelius | External advantage vs. internal character |
| Lee Kuan Yew ⟷ Richard Feynman | What works in practice vs. what is explainable in principle |
| Stanley McChrystal ⟷ John J. Pershing | Networked mission command vs. formal mass and readiness |
| Michael Hayden ⟷ Baroness Brenda Hale | Security secrecy vs. proportionality and rights |
| Barack Obama ⟷ George W. Bush | Public-trust preparedness vs. hardened continuity |
| David Addington ⟷ Dick Cheney | Lawful accountability channels vs. emergency executive power |
| Wangari Maathai ⟷ Lee Kuan Yew | Grassroots ecological legitimacy vs. technocratic developmental efficiency |
| Authoritarian Control ⟷ Arthur Chaskalson | Coercive control vs. constitutional values and dignity |
| Colonial Administrator ⟷ Mau Mau | Extractive indirect order vs. anti-colonial land and dignity grievance |
| Justice Robert Jackson ⟷ Dick Cheney | Emergency authority limits vs. emergency executive concentration |
| Justice Albie Sachs ⟷ Authoritarian Control | Repair and transitional legitimacy vs. coercive control |
| Colonial Administrator ⟷ Wangari Maathai | Extractive administration vs. ecological civic stewardship |
| Yi Sun-sin ⟷ Georgy Zhukov | Impregnable prepared defense vs. decisive offense |

## Convening profiles

Marshall is always in. Pick one profile, or name members directly with `--members`. Keep quorums to 3-8 seats plus Marshall.

| Profile | Seats besides Marshall | Use for |
| --- | --- | --- |
| `architecture` | Richard Feynman + Lee Kuan Yew + John von Neumann + J. Robert Oppenheimer + Marcus Aurelius + David Addington | Code, system design, platform, or irreversible technical capability calls |
| `strategy` | Georgy Zhukov + George Washington + Sun Tzu (孫子) + Marcus Aurelius + Queen Elizabeth I + John von Neumann | Competitive, directional, timing, and commitment decisions |
| `risk` | Marcus Aurelius + Yi Sun-sin + J. Robert Oppenheimer + Baroness Brenda Hale + Richard Feynman + Arthur Chaskalson | Downside, safety, security, rights, and failure-mode review |
| `institutional` | Augustus Caesar + Nelson Mandela + Lee Kuan Yew + Justice P.N. Bhagwati + Sejong the Great + Arthur Chaskalson | Governance, legitimacy, operating model, and stakeholder decisions |
| `policy` | Suleiman the Magnificent + Queen Elizabeth I + Sejong the Great + Arthur Chaskalson + Justice P.N. Bhagwati + David Addington | Rules, access, administration, public-facing systems, and value constraints |
| `liberation` | Toussaint Louverture + Augustus Caesar + Nelson Mandela + Baroness Brenda Hale + Mau Mau + Justice Albie Sachs | Imposed-order, self-determination, independence, and rights-heavy decisions |
| `war-game` | Blue cell + Sun Tzu + Giáp + one Justice | Adversarial stress-test where the adversary is free to win |
| `esiasa-civic-stress` | Stanley McChrystal + Michael Hayden + Wangari Maathai + David Addington + Justice P.N. Bhagwati + Sejong the Great | County/civic-stress, admin intelligence, route-backed dossiers, and legitimacy-heavy resilience work |
| `continuity` | George W. Bush + Dick Cheney + Barack Obama + Michael Hayden + Arthur Chaskalson + Justice Robert Jackson | Continuity of government, emergency authority, succession, and crisis governance |
| `pandemic-preparedness` | Barack Obama + George W. Bush + Sejong the Great + Justice P.N. Bhagwati + Baroness Brenda Hale + Wangari Maathai | Public-health readiness, civic compliance, access, rights, and whole-of-government response |
| `intelligence-oversight` | Michael Hayden + David Addington + Baroness Brenda Hale + Arthur Chaskalson + Barack Obama + Justice Robert Jackson | Intelligence products, surveillance, lawful process, civil liberties, and trust |
| `environmental-governance` | Wangari Maathai + Sejong the Great + Nelson Mandela + Lee Kuan Yew + Baroness Brenda Hale + Justice Albie Sachs | Land, environment, county resilience, public participation, and implementable stewardship |
| `oppression-audit` | Authoritarian Control + Michael Hayden + Dick Cheney + Justice Robert Jackson + Baroness Brenda Hale + Arthur Chaskalson | Detecting coercion, surveillance, emergency drift, rights violations, and dignity failure |
| `decolonization` | Colonial Administrator + Mau Mau + Toussaint Louverture + Wangari Maathai + Justice P.N. Bhagwati + Justice Albie Sachs | Land, dispossession, colonial patterns, restitution, self-determination, and repair |
| `emergency-powers` | Dick Cheney + George W. Bush + Justice Robert Jackson + Baroness Brenda Hale + David Addington + Arthur Chaskalson | Crisis authority, continuity, lawful limits, oversight, records, and sunset discipline |
| `war-cabinet` | Georgy Zhukov + Stanley McChrystal + Dick Cheney + George W. Bush + Michael Hayden + Justice Robert Jackson + David Addington | Crisis command and control: military options, executive authority, intelligence, and lawful limits under time pressure |
| `economic-thinktank` | Lee Kuan Yew + Sejong the Great + John von Neumann + Nelson Mandela + Justice P.N. Bhagwati + Wangari Maathai | Economic policy, development economics, trade-offs between growth and equity, and sustainable economic governance |
| `geopolitics` | Sun Tzu (孫子) + Augustus Caesar + Queen Elizabeth I + Suleiman the Magnificent + Võ Nguyên Giáp + George Washington + Justice P.N. Bhagwati | International relations, great-power competition, alliance strategy, diplomacy, and global power distribution |
| `space-exploration` | J. Robert Oppenheimer + Richard Feynman + John von Neumann + Marcus Aurelius + Justice P.N. Bhagwati + Arthur Chaskalson + Sejong the Great | Space policy, frontier technology ethics, resource extraction in space, access equity, and dual-use capability governance |
| `formal-science` | Richard Feynman + John von Neumann + J. Robert Oppenheimer + Marcus Aurelius + Baroness Brenda Hale + David Addington | Mathematics, cryptography, formal verification, algorithm design, and dual-use scientific capability decisions |
| `globalisation` | Lee Kuan Yew + Augustus Caesar + Nelson Mandela + Toussaint Louverture + Sejong the Great + Wangari Maathai + Justice P.N. Bhagwati | Globalisation tradeoffs, international trade, cross-border governance, development, inequality, and cultural self-determination |
| `leadership` | George Washington + Nelson Mandela + Sejong the Great + Stanley McChrystal + Marcus Aurelius + Justice P.N. Bhagwati | Leadership development, organisational culture, succession, institutional character, and leading through adversity |
| `half-conclave` | Georgy Zhukov + George Washington + Stanley McChrystal + Lee Kuan Yew + Nelson Mandela + Barack Obama + Richard Feynman + John von Neumann + J. Robert Oppenheimer + Marcus Aurelius + Sun Tzu (孫子) + Michael Hayden + Dick Cheney + Wangari Maathai + Toussaint Louverture + Baroness Brenda Hale + Justice P.N. Bhagwati | Broad multi-lens deliberation covering all major tiers without the full 33-seat conclave; suited to complex cross-domain decisions |
| `full-conclave` | Georgy Zhukov + George Washington + John J. Pershing + Võ Nguyên Giáp + Yi Sun-sin + Stanley McChrystal + Lee Kuan Yew + Augustus Caesar + Suleiman the Magnificent + Queen Elizabeth I + Sejong the Great + Nelson Mandela + Toussaint Louverture + Barack Obama + George W. Bush + Dick Cheney + Michael Hayden + Authoritarian Control + David Addington + Wangari Maathai + Colonial Administrator + Mau Mau + Baroness Brenda Hale + Justice P.N. Bhagwati + Arthur Chaskalson + Justice Robert Jackson + Justice Albie Sachs + Richard Feynman + Marcus Aurelius + John von Neumann + J. Robert Oppenheimer + Sun Tzu (孫子) | Maximum-breadth deliberation: all 32 advocate seats + Marshall on civilizational-scale, irreversible, or multi-domain decisions |

### `war-game` cells

- **Blue cell:** the seat or seats defending the current plan. Pick 1-3 based on the plan: Zhukov for decisive execution, Washington for preservation, Pershing for readiness, Yi Sun-shin for prepared defense, Lee Kuan Yew for operational viability.
- **Red cell:** Sun Tzu + Giáp. They are the adversary, free to win; they exploit deception, terrain, time, will, and asymmetric pressure.
- **White cell:** Marshall + one Justice. Marshall adjudicates grounding and directive compliance. Pick Lady Hale for proportionality/rights, Bhagwati for unheard stakeholders, or Chaskalson for foundational values and dignity. White may inject events and judge what the ledger supports.
