#!/usr/bin/env python3
"""Local Sovereign Conclave runner scaffold.

This runner does not call model providers. It selects seats from the
machine-readable roster and creates a grounded verdict scaffold that can be
filled by Claude Code, Codex, Antigravity, or a future provider-backed runner.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "conclave-roster.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def seat_index(config: dict) -> dict[str, dict]:
    return {seat["id"]: seat for seat in config["seats"]}


def profile_index(config: dict) -> dict[str, dict]:
    return {profile["id"]: profile for profile in config["profiles"]}


def display_seat(seat: dict) -> str:
    return f"{seat['id']} ({seat['tier']}; {seat['model']})"


def parse_members(raw: str) -> list[str]:
    members = []
    for member in raw.split(","):
        member = member.strip()
        if not member:
            continue
        if not member.startswith("conclave-"):
            member = f"conclave-{member}"
        members.append(member)
    return members


def choose_seats(args: argparse.Namespace, config: dict) -> tuple[str, list[str]]:
    profiles = profile_index(config)
    if args.members:
        return "--members", parse_members(args.members)
    if args.profile:
        if args.profile not in profiles:
            raise SystemExit(f"Unknown profile: {args.profile}")
        return args.profile, list(profiles[args.profile]["seats"])
    return "architecture", list(profiles["architecture"]["seats"])


def render_verdict_scaffold(problem: str, profile_id: str, seats: list[str], config: dict) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    seat_lookup = seat_index(config)
    convened = seats + [config["marshall"]]
    seat_lines = "\n".join(
        f"- **{seat_id}:** {seat_lookup[seat_id]['lens']} ({seat_lookup[seat_id]['model']})"
        for seat_id in convened
    )
    position_lines = "\n".join(
        f"- **{seat_id}:** <Round 1 recommendation> -- key claims: [E#]"
        for seat_id in seats
    )

    return f"""# Conclave Verdict -- {problem or '<decision title>'}

- **Run ID:** {timestamp}
- **Convened:** {', '.join(convened)}
- **Profile:** {profile_id}

## 1. The decision

{problem or '<State the actual question in one sentence. Include the null do-nothing option and what is being optimized.>'}

## 2. Evidence Ledger (frozen before Round 1)

| ID | Item | Source / provenance |
| --- | --- | --- |
| E1 | <Add the concrete artifact, fact, metric, file, or quote here.> | <Where it came from.> |

> Every factual claim below must reference a ledger ID, or be flagged by Marshall.

## 3. Convened lenses

{seat_lines}

## 4. Positions (Round 1 -- blind)

{position_lines}

## 5. Cross-examination (Round 2)

<Summarize which claims survived challenge, which assumptions became risks, and whether early consensus required a counterfactual pass.>

## 6. Verification (Marshall)

- `[SUPPORTED]` <claim> <- E#
- `[UNSUPPORTED]` <claim> -- would be settled by: <evidence>
- `[CONTESTED]` <claim> -- E# vs. E#
- **Directive check:** <pass, or D-# violation>

## 7. Recommendation

<Neutral synthesis. This is advice to the human, not an authorization to act.>

- **Confidence:** <low / medium / high>, and why.
- **What would change this:** <the specific finding that flips the recommendation.>
- **Unresolved dissent:** <the seat(s) that still disagree, preserved rather than averaged away.>

## 8. Decision (human)

<Left blank. The Conclave advises; the human decides.>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local Sovereign Conclave verdict scaffold.")
    parser.add_argument("problem", nargs="*", help="Decision question")
    parser.add_argument("--profile", help="Profile ID from configs/conclave-roster.json")
    parser.add_argument("--members", help="Comma-separated seat IDs or slugs")
    parser.add_argument("--list-profiles", action="store_true", help="List available profiles")
    parser.add_argument("--list-seats", action="store_true", help="List available seats")
    parser.add_argument("--stdout", action="store_true", help="Print scaffold instead of writing a file")
    parser.add_argument("--dry-run", action="store_true", help="Print selected seats without writing a file")
    parser.add_argument("--out-dir", default="verdicts", help="Output directory for verdict files")
    args = parser.parse_args()

    config = load_config()
    seats = seat_index(config)
    profiles = profile_index(config)

    if args.list_profiles:
        for profile in config["profiles"]:
            print(f"{profile['id']}: {', '.join(profile['seats'])}")
        return 0
    if args.list_seats:
        for seat in config["seats"]:
            print(display_seat(seat))
        return 0

    profile_id, selected = choose_seats(args, config)
    unknown = sorted(set(selected) - set(seats))
    if unknown:
        raise SystemExit(f"Unknown seat(s): {', '.join(unknown)}")

    problem = " ".join(args.problem).strip()
    if args.dry_run:
        print(f"profile={profile_id}")
        print("seats=" + ",".join(selected + [config["marshall"]]))
        return 0

    rendered = render_verdict_scaffold(problem, profile_id, selected, config)
    if args.stdout:
        print(rendered)
        return 0

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"verdict-{stamp}.md"
    out_path.write_text(rendered, encoding="utf-8")
    print(out_path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
