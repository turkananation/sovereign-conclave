#!/usr/bin/env python3
"""Validate Sovereign Conclave repo invariants."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from evidence_ledger import load_ledger_json, validate_ledger_document


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "conclave-roster.json"
FOOTER = "Cite the Evidence Ledger (`E#`) for any factual claim. Max 400 words in Round 1."
MODEL_VALUES = {"sonnet", "opus"}


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    try:
        _, raw, _ = text.split("---", 2)
    except ValueError:
        return {}
    values: dict[str, str] = {}
    for line in raw.strip().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def markdown_roster_ids() -> set[str]:
    roster = read_text(ROOT / "roster.md")
    active = roster.split("## Library status", 1)[0]
    return set(re.findall(r"`(conclave-[^`]+)`", active))


def provider_slot_ids() -> set[str]:
    path = ROOT / "configs" / "provider-model-slots.example.yaml"
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in read_text(path).splitlines():
        match = re.match(r"\s*(conclave-[a-z0-9-]+):\s*\w+", line)
        if match:
            ids.add(match.group(1))
    return ids


def citation_ids(text: str) -> set[str]:
    ids: set[str] = set()
    for bracket in re.findall(r"\[([^\]]*E\d+[^\]]*)\]", text):
        for start, end in re.findall(r"E(\d+)(?:\s*-\s*E?(\d+))?", bracket):
            if end:
                for value in range(int(start), int(end) + 1):
                    ids.add(f"E{value}")
            else:
                ids.add(f"E{int(start)}")
    return ids


def validate_demo_verdicts(failures: list[str]) -> None:
    verdict_dir = ROOT / "demos" / "verdicts"
    for path in sorted(verdict_dir.glob("*.md")):
        text = read_text(path)
        rel = path.relative_to(ROOT)
        if "## 2. Evidence Ledger" not in text:
            fail(f"{rel}: missing Evidence Ledger section", failures)
            continue
        if "| ID | Item | Source / provenance | Handling |" not in text:
            fail(f"{rel}: Evidence Ledger must use the four-column standard", failures)

        ledger_section = text.split("## 2. Evidence Ledger", 1)[1].split("\n## ", 1)[0]
        ledger_ids = set(re.findall(r"^\| (E\d+) \|", ledger_section, flags=re.MULTILINE))
        if not ledger_ids:
            fail(f"{rel}: Evidence Ledger has no E# rows", failures)
            continue

        used_ids = citation_ids(text)
        unknown = sorted(used_ids - ledger_ids, key=lambda item: int(item[1:]))
        if unknown:
            fail(f"{rel}: cites unknown ledger IDs {unknown}", failures)


def validate_demo_ledgers(failures: list[str]) -> None:
    ledger_dir = ROOT / "demos" / "evidence-ledgers"
    for path in sorted(ledger_dir.glob("*.json")):
        rel = path.relative_to(ROOT)
        try:
            document = load_ledger_json(path)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            fail(f"{rel}: invalid JSON ledger: {error}", failures)
            continue
        for issue in validate_ledger_document(document):
            fail(f"{rel}: {issue}", failures)


def validate_agent(seat: dict[str, object], failures: list[str]) -> None:
    seat_id = str(seat["id"])
    seat_type = str(seat["type"])
    path = ROOT / str(seat["path"])

    if not path.exists():
        fail(f"{seat_id}: missing agent file {path.relative_to(ROOT)}", failures)
        return

    text = read_text(path)
    fm = frontmatter(text)
    if fm.get("name") != seat_id:
        fail(f"{seat_id}: frontmatter name mismatch", failures)
    if not fm.get("description"):
        fail(f"{seat_id}: missing frontmatter description", failures)
    if fm.get("model") != seat.get("model"):
        fail(f"{seat_id}: model mismatch between config and agent", failures)
    if fm.get("model") not in MODEL_VALUES:
        fail(f"{seat_id}: invalid model {fm.get('model')!r}", failures)

    if seat_type != "verifier" and "not a capability" not in text:
        fail(f"{seat_id}: missing lens-not-capability language", failures)

    if seat_type == "advocate":
        required = [
            "**Your stance:**",
            "**How you argue:**",
            "**Your characteristic bias",
            "**You are NOT:**",
            "**Polarity partner:**",
            FOOTER,
        ]
        for needle in required:
            if needle not in text:
                fail(f"{seat_id}: missing {needle}", failures)
        move_count = sum(1 for line in text.splitlines() if line.startswith("- "))
        if not 3 <= move_count <= 4:
            fail(f"{seat_id}: expected 3-4 argument moves, found {move_count}", failures)
    elif seat_type == "justice":
        required = [
            "**Your check:**",
            "**How you check:**",
            "**You are NOT:**",
            "**Your authority:**",
            FOOTER,
        ]
        for needle in required:
            if needle not in text:
                fail(f"{seat_id}: missing {needle}", failures)
        if "**Polarity partner:**" in text:
            fail(f"{seat_id}: Justice must not have a polarity partner", failures)
    elif seat_type == "verifier":
        if "structural guardrail" not in text:
            fail(f"{seat_id}: verifier must identify as a structural guardrail", failures)
        if "[SUPPORTED]" not in text or "[UNSUPPORTED]" not in text:
            fail(f"{seat_id}: verifier must define support tags", failures)
    else:
        fail(f"{seat_id}: unknown type {seat_type}", failures)


def main() -> int:
    failures: list[str] = []
    config = json.loads(read_text(CONFIG_PATH))

    seats = config.get("seats", [])
    profiles = config.get("profiles", [])
    seat_ids = [seat["id"] for seat in seats]
    seat_id_set = set(seat_ids)
    agent_ids = {path.stem for path in (ROOT / "agents").glob("conclave-*.md")}
    roster_ids = markdown_roster_ids()

    if len(seat_ids) != len(seat_id_set):
        fail("configs/conclave-roster.json: duplicate seat IDs", failures)
    if seat_id_set != agent_ids:
        fail(
            "config/agent mismatch: "
            f"missing_config={sorted(agent_ids - seat_id_set)} "
            f"missing_agent={sorted(seat_id_set - agent_ids)}",
            failures,
        )
    if seat_id_set != roster_ids:
        fail(
            "config/roster.md mismatch: "
            f"missing_roster={sorted(seat_id_set - roster_ids)} "
            f"missing_config={sorted(roster_ids - seat_id_set)}",
            failures,
        )
    if config.get("marshall") != "conclave-marshall":
        fail("marshall must be conclave-marshall", failures)
    if "conclave-marshall" not in seat_id_set:
        fail("conclave-marshall must exist in seats", failures)

    for seat in seats:
        validate_agent(seat, failures)
    validate_demo_verdicts(failures)
    validate_demo_ledgers(failures)

    profile_ids = [profile["id"] for profile in profiles]
    if len(profile_ids) != len(set(profile_ids)):
        fail("configs/conclave-roster.json: duplicate profile IDs", failures)
    min_seats = int(config["quorum"]["min_seats"])
    max_seats = int(config["quorum"]["max_seats"])
    for profile in profiles:
        profile_id = profile["id"]
        profile_seats = profile["seats"]
        if "conclave-marshall" in profile_seats:
            fail(f"profile {profile_id}: must not list Marshall directly", failures)
        unknown = sorted(set(profile_seats) - seat_id_set)
        if unknown:
            fail(f"profile {profile_id}: unknown seats {unknown}", failures)
        if not min_seats <= len(profile_seats) <= max_seats:
            fail(f"profile {profile_id}: quorum size {len(profile_seats)} outside {min_seats}-{max_seats}", failures)

    for pair in config.get("polarity_pairs", []):
        for side in ("a", "b"):
            if pair[side] not in seat_id_set:
                fail(f"polarity pair references unknown seat {pair[side]}", failures)

    provider_ids = provider_slot_ids()
    missing_provider_slots = sorted(seat_id_set - provider_ids)
    if missing_provider_slots:
        fail(f"provider-model-slots.example.yaml missing seats {missing_provider_slots}", failures)

    required_docs = [
        "CHANGELOG.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "docs/FEATURE_ROADMAP.md",
        "docs/PROGRESS_TRACKER.md",
        "docs/QUICKSTART.md",
        "docs/CONCEPTS.md",
        "docs/EVIDENCE_LEDGER.md",
        "docs/SEAT_EXPANSION_RATIONALE.md",
        "demos/evidence-ledger-template.md",
        "demos/evidence-ledgers/pandemic-preparedness-county-response.json",
        "schemas/evidence-ledger.schema.json",
        "ledgers/.gitkeep",
    ]
    for doc in required_docs:
        if not (ROOT / doc).exists():
            fail(f"missing required document {doc}", failures)

    if failures:
        print("Validation failed:")
        for item in failures:
            print(f"- {item}")
        return 1

    print("Validation passed")
    print(f"seats={len(seats)} profiles={len(profiles)} polarity_pairs={len(config.get('polarity_pairs', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
