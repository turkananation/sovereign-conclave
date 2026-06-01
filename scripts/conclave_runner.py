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
from typing import Any

from evidence_ledger import (
    ledger_document,
    load_ledger_json,
    validate_ledger_document,
    write_ledger_json,
)


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


def resolve_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def provider_config_path(explicit: str | None) -> Path:
    if explicit:
        return resolve_path(explicit)
    real = ROOT / "configs" / "provider-model-slots.yaml"
    return real if real.exists() else ROOT / "configs" / "provider-model-slots.example.yaml"


def next_evidence_id(used_ids: set[str], start: int = 1) -> str:
    value = start
    while f"E{value}" in used_ids:
        value += 1
    return f"E{value}"


def assign_evidence_ids(entries: list[dict[str, Any]], *, renumber: bool = False) -> None:
    if renumber:
        # Merging multiple source ledgers: each carries its own E1.. sequence,
        # so discard incoming IDs and lay down one contiguous sequence.
        for index, entry in enumerate(entries, start=1):
            entry["id"] = f"E{index}"
        return

    used_ids: set[str] = set()
    for entry in entries:
        entry_id = entry.get("id")
        if not isinstance(entry_id, str):
            continue
        if entry_id in used_ids:
            raise SystemExit(f"Duplicate evidence ID while assembling ledger: {entry_id}")
        used_ids.add(entry_id)

    cursor = 1
    for entry in entries:
        if entry.get("id"):
            continue
        entry_id = next_evidence_id(used_ids, cursor)
        entry["id"] = entry_id
        used_ids.add(entry_id)
        cursor = int(entry_id[1:]) + 1


def source_provenance(entry: dict[str, Any]) -> str:
    pieces = []
    source = entry.get("source", "")
    provenance = entry.get("provenance", "")
    content_hash = entry.get("content_hash", "")
    if source:
        pieces.append(str(source))
    if provenance:
        pieces.append(str(provenance))
    if content_hash:
        pieces.append(str(content_hash))
    return "; ".join(pieces)


def load_ledger_entries(raw_path: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = resolve_path(raw_path)
    if not path.is_file():
        raise SystemExit(f"Ledger file not found: {raw_path}")
    try:
        document = load_ledger_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"Could not load ledger file {raw_path}: {error}") from error

    failures = validate_ledger_document(document)
    if failures:
        details = "\n".join(f"- {failure}" for failure in failures)
        raise SystemExit(f"Invalid ledger file {raw_path}:\n{details}")
    return document, [dict(entry) for entry in document["entries"]]


def build_evidence_document(args: argparse.Namespace, problem: str, timestamp: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    loaded_documents: list[dict[str, Any]] = []

    for raw_path in args.ledger_file:
        document, ledger_entries = load_ledger_entries(raw_path)
        loaded_documents.append(document)
        entries.extend(ledger_entries)

    for raw_path in args.evidence_file:
        path = resolve_path(raw_path)
        if not path.is_file():
            raise SystemExit(f"Evidence file not found: {raw_path}")
        digest = sha256_digest(path)
        entries.append(
            {
                "item": f"File: `{display_path(path)}`",
                "source_type": "local_file",
                "source": display_path(path),
                "provenance": "Local file supplied with --evidence-file at runner invocation",
                "handling": "Freeze file contents at run start; quote exact lines or snippets before relying on details.",
                "content_hash": f"sha256:{digest}",
            }
        )

    for raw_note in args.evidence_note:
        note = raw_note.strip()
        if not note:
            continue
        entries.append(
            {
                "item": f"Note: {note}",
                "source_type": "user_assertion",
                "source": "--evidence-note",
                "provenance": "User-supplied note at runner invocation",
                "handling": "Treat only as asserted input; do not infer facts beyond the note.",
            }
        )

    # A single imported ledger keeps its own IDs; merging two or more renumbers
    # the combined set so their overlapping E1.. sequences cannot collide.
    assign_evidence_ids(entries, renumber=len(loaded_documents) >= 2)

    if loaded_documents and len(loaded_documents) == 1 and not args.evidence_file and not args.evidence_note:
        source_document = dict(loaded_documents[0])
        source_document["entries"] = entries
        return source_document

    decision = problem or "<decision title>"
    ledger_id = args.ledger_id or f"ledger-{timestamp.replace(':', '').replace('-', '')}"
    notes = ""
    if loaded_documents:
        source_ids = ", ".join(str(document.get("ledger_id")) for document in loaded_documents)
        notes = f"Merged from ledger file(s): {source_ids}."
    return ledger_document(
        ledger_id=ledger_id,
        decision=decision,
        prepared_by=args.prepared_by,
        freeze_time_utc=timestamp,
        sensitivity=args.ledger_sensitivity,
        entries=entries,
        ledger_status="frozen" if entries else "draft",
        notes=notes,
    )


def choose_seats(args: argparse.Namespace, config: dict) -> tuple[str, list[str]]:
    profiles = profile_index(config)
    if args.members:
        return "--members", parse_members(args.members)
    if args.profile:
        if args.profile not in profiles:
            raise SystemExit(f"Unknown profile: {args.profile}")
        return args.profile, list(profiles[args.profile]["seats"])
    default_profile = config.get("default_profile", "architecture")
    if default_profile not in profiles:
        raise SystemExit(f"Configured default_profile is unknown: {default_profile}")
    return default_profile, list(profiles[default_profile]["seats"])


def render_evidence_ledger(ledger: dict[str, Any], timestamp: str) -> str:
    entries = ledger.get("entries", [])
    if not entries:
        return f"""**Freeze time:** {timestamp}
**Ledger status:** Empty placeholder. Add concrete artifacts before Round 1.

| ID | Item | Source / provenance | Handling |
| --- | --- | --- | --- |
| E1 | <Add the concrete artifact, fact, metric, file, or quote here.> | <Where it came from.> | <How to treat it: quoted fact, local file, user assertion, public source, redacted source, etc.> |"""

    freeze_time = str(ledger.get("freeze_time_utc") or timestamp)
    ledger_status = str(ledger.get("ledger_status") or "frozen")
    ledger_id = str(ledger.get("ledger_id") or "<not set>")
    sensitivity = str(ledger.get("sensitivity") or "<not set>")
    rows = []
    for entry in entries:
        rows.append(
            "| {id} | {item} | {source} | {handling} |".format(
                id=entry["id"],
                item=markdown_cell(entry["item"]),
                source=markdown_cell(source_provenance(entry)),
                handling=markdown_cell(entry["handling"]),
            )
        )
    return "\n".join(
        [
            f"**Ledger ID:** {ledger_id}",
            f"**Freeze time:** {freeze_time}",
            f"**Ledger status:** {ledger_status}",
            f"**Sensitivity:** {sensitivity}",
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
    evidence_ledger_document: dict[str, Any],
    timestamp: str,
) -> str:
    seat_lookup = seat_index(config)
    convened = seats + [config["marshall"]]
    seat_lines = "\n".join(
        f"- **{seat_id}:** {seat_lookup[seat_id]['lens']} ({seat_lookup[seat_id]['model']})"
        for seat_id in convened
    )
    def position_line(seat_id: str) -> str:
        seat = seat_lookup[seat_id]
        if seat.get("type") in {"justice", "verifier"}:
            return f"- **{seat_id}** ({seat['lens']}): <structural check; states a bound, not an option preference>"
        return f"- **{seat_id}:** <Round 1 recommendation> -- key claims: [E#]"

    position_lines = "\n".join(position_line(seat_id) for seat_id in seats)
    evidence_ledger = render_evidence_ledger(evidence_ledger_document, timestamp)

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

<Left blank. The Sovereign Conclave advises; the human decides.>
"""


def run_provider_mode(args, config, profile_id, selected, problem, evidence_ledger_document, evidence_entries, timestamp):
    """Opt-in provider-backed run. Returns an exit code, or None to fall back to the scaffold."""
    import provider_runner as pr

    cfg_path = provider_config_path(args.provider_config)
    cfg_text = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else ""
    provider_cfg = pr.parse_provider_config(cfg_text)
    client = pr.get_client()
    seat_lookup = seat_index(config)
    convened = selected + [config["marshall"]]

    if client is None:
        print(
            "warning: --provider-run requested but no provider is reachable "
            "(set CONCLAVE_PROVIDER_CMD or ANTHROPIC_API_KEY); falling back to the deterministic scaffold.",
            file=sys.stderr,
        )
        return None

    if args.dry_run:
        print(pr.routing_plan(convened, seat_lookup, provider_cfg, client.name))
        return 0

    ledger_section = render_evidence_ledger(evidence_ledger_document, timestamp)

    def agent_text(seat_id: str) -> str:
        return (ROOT / seat_lookup[seat_id]["path"]).read_text(encoding="utf-8")

    result = pr.run_deliberation(
        convened=convened,
        seat_lookup=seat_lookup,
        agent_text=agent_text,
        provider_cfg=provider_cfg,
        client=client,
        problem=problem,
        ledger_section=ledger_section,
        timeout=args.provider_timeout,
    )

    if args.write_ledger and evidence_entries:
        failures = validate_ledger_document(evidence_ledger_document)
        if failures:
            details = "\n".join(f"- {failure}" for failure in failures)
            raise SystemExit(f"Cannot write invalid ledger:\n{details}")
        write_ledger_json(resolve_path(args.write_ledger), evidence_ledger_document)

    if args.stdout:
        print(
            pr.render_provider_verdict(
                problem=problem, profile_id=profile_id, convened=convened,
                seat_lookup=seat_lookup, ledger_section=ledger_section, result=result,
                timestamp=timestamp, client_name=client.name, transcript_rel=None,
            )
        )
        return 0

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = timestamp.replace(":", "").replace("-", "")
    out_path = out_dir / f"verdict-{stamp}.md"
    counter = 1
    while out_path.exists():
        out_path = out_dir / f"verdict-{stamp}-{counter}.md"
        counter += 1
    transcript_path = out_dir / f"{out_path.stem}.transcript.json"

    rendered = pr.render_provider_verdict(
        problem=problem, profile_id=profile_id, convened=convened,
        seat_lookup=seat_lookup, ledger_section=ledger_section, result=result,
        timestamp=timestamp, client_name=client.name, transcript_rel=display_path(transcript_path),
    )
    out_path.write_text(rendered, encoding="utf-8")
    transcript_path.write_text(
        json.dumps(
            {
                "run_id": timestamp,
                "profile": profile_id,
                "convened": convened,
                "client": client.name,
                "errors": result.errors,
                "calls": result.transcript,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(display_path(out_path))
    print(display_path(transcript_path))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local Sovereign Conclave verdict scaffold.")
    parser.add_argument("problem", nargs="*", help="Decision question")
    parser.add_argument("--profile", help="Profile ID from configs/conclave-roster.json")
    parser.add_argument("--members", help="Comma-separated seat IDs or slugs")
    parser.add_argument("--ledger-file", action="append", default=[], help="Machine-readable Evidence Ledger JSON to load")
    parser.add_argument("--validate-ledger", action="append", default=[], help="Validate machine-readable Evidence Ledger JSON and exit")
    parser.add_argument("--write-ledger", help="Write the assembled machine-readable Evidence Ledger JSON to this path")
    parser.add_argument("--ledger-id", help="Ledger ID to use when writing a generated ledger")
    parser.add_argument("--prepared-by", default="local-runner", help="Prepared-by value for generated ledger JSON")
    parser.add_argument(
        "--ledger-sensitivity",
        default="internal",
        choices=["public", "internal", "confidential", "secret-derived-not-quoted"],
        help="Sensitivity label for generated ledger JSON",
    )
    parser.add_argument("--evidence-file", action="append", default=[], help="File to freeze into the Evidence Ledger")
    parser.add_argument("--evidence-note", action="append", default=[], help="Explicit note or claim to freeze into the Evidence Ledger")
    parser.add_argument("--list-profiles", action="store_true", help="List available profiles")
    parser.add_argument("--list-seats", action="store_true", help="List available seats")
    parser.add_argument("--stdout", action="store_true", help="Print scaffold instead of writing a file")
    parser.add_argument("--dry-run", action="store_true", help="Print selected seats without writing a file")
    parser.add_argument("--out-dir", default="verdicts", help="Output directory for verdict files")
    parser.add_argument("--provider-run", action="store_true", help="Opt-in: run real provider-backed deliberation (needs env keys; OFF by default)")
    parser.add_argument("--provider-timeout", type=float, default=60.0, help="Per-call timeout in seconds for provider mode")
    parser.add_argument("--provider-config", help="Provider slot YAML (default: configs/provider-model-slots.yaml, else the example)")
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
    if args.validate_ledger:
        for raw_path in args.validate_ledger:
            load_ledger_entries(raw_path)
            print(f"{raw_path}: valid")
        return 0

    profile_id, selected = choose_seats(args, config)
    unknown = sorted(set(selected) - set(seats))
    if unknown:
        raise SystemExit(f"Unknown seat(s): {', '.join(unknown)}")
    problem = " ".join(args.problem).strip()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    evidence_ledger_document = build_evidence_document(args, problem, timestamp)
    evidence_entries = evidence_ledger_document.get("entries", [])
    if evidence_entries:
        failures = validate_ledger_document(evidence_ledger_document)
        if failures:
            details = "\n".join(f"- {failure}" for failure in failures)
            raise SystemExit(f"Invalid assembled ledger:\n{details}")

    if args.provider_run:
        provider_exit = run_provider_mode(
            args, config, profile_id, selected, problem,
            evidence_ledger_document, evidence_entries, timestamp,
        )
        if provider_exit is not None:
            return provider_exit

    if args.dry_run:
        if args.write_ledger:
            print("warning: --write-ledger is ignored under --dry-run", file=sys.stderr)
        print(f"profile={profile_id}")
        print("seats=" + ",".join(selected + [config["marshall"]]))
        if evidence_entries:
            print(f"evidence_items={len(evidence_entries)}")
        return 0

    if args.write_ledger:
        if not evidence_entries:
            raise SystemExit("--write-ledger requires at least one --ledger-file, --evidence-file, or --evidence-note item")
        failures = validate_ledger_document(evidence_ledger_document)
        if failures:
            details = "\n".join(f"- {failure}" for failure in failures)
            raise SystemExit(f"Cannot write invalid ledger:\n{details}")
        write_ledger_json(resolve_path(args.write_ledger), evidence_ledger_document)

    rendered = render_verdict_scaffold(problem, profile_id, selected, config, evidence_ledger_document, timestamp)
    if args.stdout:
        print(rendered)
        return 0

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    # Reuse the single run timestamp (so the filename matches the in-file Run ID)
    # and never overwrite a prior verdict written in the same second.
    stamp = timestamp.replace(":", "").replace("-", "")
    out_path = out_dir / f"verdict-{stamp}.md"
    counter = 1
    while out_path.exists():
        out_path = out_dir / f"verdict-{stamp}-{counter}.md"
        counter += 1
    out_path.write_text(rendered, encoding="utf-8")
    print(display_path(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
