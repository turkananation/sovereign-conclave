# The Conclave Roster

The Conclave is a **library** of seats, not a standing assembly. You convene a small **quorum** per decision. The library can be as large as you like; the meeting stays small (3–8 seats + Marshall). You only write an agent file for a seat you actually convene — the rest live here as a documented bench until you summon them.

This is the answer to "how many personas": the library is open-ended, the meeting is small, and a seat earns inclusion only by arguing a stance no current seat covers.

## Active seats (agent files written)

| Seat | Tier | Lens | Model |
| --- | --- | --- | --- |
| `conclave-zhukov` | General | Decisive force, initiative, operational reach | sonnet |
| `conclave-lee-kuan-yew` | Sovereign | What works at scale, resource discipline | sonnet |
| `conclave-feynman` | Inner Sanctum | First principles, refuses unexplained complexity | sonnet |
| `conclave-aurelius` | Inner Sanctum | Downside containment, restraint, moral clarity | opus |
| `conclave-marshall` | Justice (verifier) | Grounds claims, flags unsupported, may veto — **convened always** | opus |

These five are deliberately orthogonal: offense vs. restraint (Zhukov ⟷ Aurelius), works-in-practice vs. explainable-from-principles (Lee Kuan Yew ⟷ Feynman), and a structural guardrail that holds no opinion (Marshall).

## The bench — your pantheon (write an agent file when first convened)

Copy `agents/_TEMPLATE.md` and fill in the lens. Tiers from your design:

- **Generals (kinetic / strategy):** Washington, Pershing, Giáp, Yi Sun-shin
- **Sovereigns (governance / policy):** Augustus, Suleiman I, Elizabeth I, Sejong, Mandela, Toussaint L'Ouverture
- **Justices (verification):** Lady Hale, Bhagwati, Chaskalson — *structural seats; keep them opinion-free and grounded, like Marshall*
- **Inner Sanctum (science / logic):** von Neumann, Oppenheimer, Sun Tzu

Add a seat only for **orthogonality** — if it argues a stance no current seat covers. Two seats that agree are one seat and a cost.

## Convening profiles

Marshall is always in. Pick one profile, or name members directly with `--members`.

| Profile | Seats (besides Marshall) | Use for |
| --- | --- | --- |
| `architecture` | Feynman + Lee Kuan Yew + *(von Neumann)* | Code / system-design calls |
| `strategy` | Zhukov + *(Sun Tzu)* + Aurelius | Competitive / directional moves |
| `risk` | Aurelius + Feynman + *(Yi Sun-shin)* | Downside, security, failure modes |
| `war-game` | Zhukov (blue) + *(Sun Tzu, red)* + Aurelius (white / adjudicator) | Adversarial stress-test |
| `institutional` | Lee Kuan Yew + *(a Justice)* + Aurelius | Governance / legitimacy decisions |

Seats in *(parentheses)* are on the bench — write their agent file before using a profile that names them.
