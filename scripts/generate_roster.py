#!/usr/bin/env python3
"""Generate roster.md from configs/conclave-roster.json.

`configs/conclave-roster.json` is the single source of truth for seats,
polarity pairs, and profiles. `roster.md` is a rendered view of it. Run with
`--write` to regenerate it and `--check` (CI) to fail on drift.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "conclave-roster.json"
ROSTER_PATH = ROOT / "roster.md"

INTRO = """# The Sovereign Conclave Roster

The Sovereign Conclave is a **library** of seats, not a standing assembly. You convene a small **quorum** per decision: 3-8 seats plus Marshall. The library can be large; the meeting stays small. A seat earns inclusion only by arguing a stance no current seat covers, or by enforcing a structural check no other Justice owns.

Marshall is convened in every deliberation. The other Justices are optional structural checks: they hold no opinion on which option should win."""

LIBRARY_STATUS = """The {count}-seat library is written. It includes the core pantheon, eSiasa-oriented extension seats, danger lenses for ugly governance logics, and additional Justice checks. Add a new seat the same way only when it brings a stance or structural check no existing seat covers:

1. Copy `agents/_TEMPLATE.md`.
2. Give the seat one clear lens, an owned bias, a "You are NOT" boundary, and a polarity partner.
3. Keep the seat as a lens, never a claim that the model gained a new capability.

Two seats that agree are one seat and a cost."""

# The war-game profile row is editorial (cells, not a flat seat list).
WARGAME_PROFILE_SEATS = "Blue cell + Sun Tzu + Giáp + one Justice"

WARGAME_CELLS = """### `war-game` cells

- **Blue cell:** the seat or seats defending the current plan. Pick 1-3 based on the plan: Zhukov for decisive execution, Washington for preservation, Pershing for readiness, Yi Sun-shin for prepared defense, Lee Kuan Yew for operational viability.
- **Red cell:** Sun Tzu + Giáp. They are the adversary, free to win; they exploit deception, terrain, time, will, and asymmetric pressure.
- **White cell:** Marshall + one Justice. Marshall adjudicates grounding and directive compliance. Pick Lady Hale for proportionality/rights, Bhagwati for unheard stakeholders, or Chaskalson for foundational values and dignity. White may inject events and judge what the ledger supports."""


def render(config: dict) -> str:
    seats = config["seats"]
    marshall = config["marshall"]
    display = {seat["id"]: seat["display_name"] for seat in seats}

    lines: list[str] = [INTRO, "", "## Active seats (agent files written)", ""]
    lines += ["| Seat | Tier | Lens | Model |", "| --- | --- | --- | --- |"]
    for seat in seats:
        tier = "Justice (always)" if seat["id"] == marshall else seat["tier"]
        lines.append(f"| `{seat['id']}` | {tier} | {seat['lens']} | {seat['model']} |")

    lines += ["", "## Library status", "", LIBRARY_STATUS.format(count=len(seats))]

    lines += ["", "## Polarity pairs", "",
              "These are the canonical contrasts. Use them to build small quorums with real disagreement.",
              "", "| Pair | Contrast |", "| --- | --- |"]
    for pair in config["polarity_pairs"]:
        lines.append(f"| {display[pair['a']]} ⟷ {display[pair['b']]} | {pair['contrast']} |")

    lines += ["", "## Convening profiles", "",
              "Marshall is always in. Pick one profile, or name members directly with `--members`. Keep quorums to 3-8 seats plus Marshall.",
              "", "| Profile | Seats besides Marshall | Use for |", "| --- | --- | --- |"]
    for profile in config["profiles"]:
        if profile["id"] == "war-game":
            seats_str = WARGAME_PROFILE_SEATS
        else:
            seats_str = " + ".join(display[seat_id] for seat_id in profile["seats"])
        lines.append(f"| `{profile['id']}` | {seats_str} | {profile['use_for']} |")

    lines += ["", WARGAME_CELLS, ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate roster.md from the machine-readable config.")
    parser.add_argument("--write", action="store_true", help="Write roster.md")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if roster.md is stale")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    rendered = render(config)

    if args.check:
        current = ROSTER_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print("roster.md is out of sync with configs/conclave-roster.json.")
            print("Run: python3 scripts/generate_roster.py --write")
            import difflib

            diff = difflib.unified_diff(
                current.splitlines(), rendered.splitlines(),
                fromfile="roster.md", tofile="generated", lineterm="",
            )
            print("\n".join(diff))
            return 1
        print("roster.md is in sync")
        return 0

    if args.write:
        ROSTER_PATH.write_text(rendered, encoding="utf-8")
        print(f"wrote {ROSTER_PATH.relative_to(ROOT)}")
        return 0

    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
