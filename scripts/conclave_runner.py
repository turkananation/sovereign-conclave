#!/usr/bin/env python3
"""Local Sovereign Conclave runner scaffold.

This runner does not call model providers. It selects seats from the
machine-readable roster and creates a grounded verdict scaffold that can be
filled by Claude Code, Codex, Antigravity, or a future provider-backed runner.
"""

from __future__ import annotations

import argparse
import hashlib
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


def markdown_cell(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha256_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_evidence_entries(args: argparse.Namespace) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []

    for raw_path in args.evidence_file:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path = path.resolve()
        if not path.is_file():
            raise SystemExit(f"Evidence file not found: {raw_path}")
        entries.append(
            {
                "item": f"File: `{display_path(path)}`",
                "source": f"Local file supplied with --evidence-file; sha256={sha256_digest(path)[:16]}",
                "handling": "Freeze file contents at run start; quote exact lines or snippets before relying on details.",
            }
        )

    for raw_note in args.evidence_note:
        note = raw_note.strip()
        if not note:
            continue
        entries.append(
            {
                "item": f"Note: {note}",
                "source": "User-supplied note at runner invocation",
                "handling": "Treat only as asserted input; do not infer facts beyond the note.",
            }
        )

    return entries


def choose_seats(args: argparse.Namespace, config: dict) -> tuple[str, list[str]]:
    profiles = profile_index(config)
    if args.members:
        return "--members", parse_members(args.members)
    if args.profile:
        if args.profile not in profiles:
            raise SystemExit(f"Unknown profile: {args.profile}")
        return args.profile, list(profiles[args.profile]["seats"])
    return "architecture", list(profiles["architecture"]["seats"])


def render_evidence_ledger(entries: list[dict[str, str]], timestamp: str) -> str:
    if not entries:
        return f"""**Freeze time:** {timestamp}
**Ledger status:** Empty placeholder. Add concrete artifacts before Round 1.

| ID | Item | Source / provenance | Handling |
| --- | --- | --- | --- |
| E1 | <Add the concrete artifact, fact, metric, file, or quote here.> | <Where it came from.> | <How to treat it: quoted fact, local file, user assertion, public source, redacted source, etc.> |"""

    rows = []
    for index, entry in enumerate(entries, start=1):
        rows.append(
            "| E{index} | {item} | {source} | {handling} |".format(
                index=index,
                item=markdown_cell(entry["item"]),
                source=markdown_cell(entry["source"]),
                handling=markdown_cell(entry["handling"]),
            )
        )
    return "\n".join(
        [
            f"**Freeze time:** {timestamp}",
            "**Ledger status:** Frozen before Round 1.",
            "",
            "| ID | Item | Source / provenance | Handling |",
            "| --- | --- | --- | --- |",
            *rows,
        ]
    )


def render_verdict_scaffold(
    problem: str,
    profile_id: str,
    seats: list[str],
    config: dict,
    evidence_entries: list[dict[str, str]],
) -> str:
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
    evidence_ledger = render_evidence_ledger(evidence_entries, timestamp)

    return f"""# Conclave Verdict -- {problem or '<decision title>'}

- **Run ID:** {timestamp}
- **Convened:** {', '.join(convened)}
- **Profile:** {profile_id}

## 1. The decision

{problem or '<State the actual question in one sentence. Include the null do-nothing option and what is being optimized.>'}

## 2. Evidence Ledger (frozen before Round 1)

{evidence_ledger}

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
    parser.add_argument("--evidence-file", action="append", default=[], help="File to freeze into the Evidence Ledger")
    parser.add_argument("--evidence-note", action="append", default=[], help="Explicit note or claim to freeze into the Evidence Ledger")
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
    evidence_entries = build_evidence_entries(args)

    problem = " ".join(args.problem).strip()
    if args.dry_run:
        print(f"profile={profile_id}")
        print("seats=" + ",".join(selected + [config["marshall"]]))
        if evidence_entries:
            print(f"evidence_items={len(evidence_entries)}")
        return 0

    rendered = render_verdict_scaffold(problem, profile_id, selected, config, evidence_entries)
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
