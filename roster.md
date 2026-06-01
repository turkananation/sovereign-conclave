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
| `conclave-lee-kuan-yew` | Sovereign | What works at scale, resource discipline | sonnet |
| `conclave-augustus` | Sovereign | Durable institutions, legitimacy, consolidation | opus |
| `conclave-suleiman` | Sovereign | Codified law, uniform administration, cohesion | sonnet |
| `conclave-elizabeth` | Sovereign | Optionality, ambiguity, parsimony, balancing rivals | opus |
| `conclave-sejong` | Sovereign | Capability of the governed; accessible systems | sonnet |
| `conclave-mandela` | Sovereign | Reconciliation, legitimacy, durable peace | opus |
| `conclave-toussaint` | Sovereign | Liberation, self-determination, sovereignty from below | sonnet |
| `conclave-marshall` | Justice (always) | Evidence-grounding and directive check | opus |
| `conclave-lady-hale` | Justice | Proportionality and rights check | opus |
| `conclave-bhagwati` | Justice | Access, standing, and missing-stakeholder check | opus |
| `conclave-chaskalson` | Justice | Constitutional values and dignity check | opus |
| `conclave-feynman` | Inner Sanctum | First principles, refuses unexplained complexity | sonnet |
| `conclave-aurelius` | Inner Sanctum | Downside containment, restraint, moral clarity | opus |
| `conclave-von-neumann` | Inner Sanctum | Formal modeling, game theory, expected value | opus |
| `conclave-oppenheimer` | Inner Sanctum | Capability, consequence, dual-use control | opus |
| `conclave-sun-tzu` | Inner Sanctum | Win before fighting; positioning and deception | opus |

## Library status

The named pantheon is fully written. Add a new seat the same way only when it brings a stance or structural check no existing seat covers:

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

### `war-game` cells

- **Blue cell:** the seat or seats defending the current plan. Pick 1-3 based on the plan: Zhukov for decisive execution, Washington for preservation, Pershing for readiness, Yi Sun-shin for prepared defense, Lee Kuan Yew for operational viability.
- **Red cell:** Sun Tzu + Giáp. They are the adversary, free to win; they exploit deception, terrain, time, will, and asymmetric pressure.
- **White cell:** Marshall + one Justice. Marshall adjudicates grounding and directive compliance. Pick Lady Hale for proportionality/rights, Bhagwati for unheard stakeholders, or Chaskalson for foundational values and dignity. White may inject events and judge what the ledger supports.
