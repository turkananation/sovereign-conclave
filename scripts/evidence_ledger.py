"""Evidence Ledger helpers for Sovereign Conclave."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0.0"
LEDGER_ID_RE = re.compile(r"^E[1-9][0-9]*$")
LEDGER_STATUS_VALUES = {"draft", "frozen", "post_freeze_appended"}
SENSITIVITY_VALUES = {"public", "internal", "confidential", "secret-derived-not-quoted"}
SOURCE_TYPE_VALUES = {
    "repository_file",
    "local_file",
    "user_assertion",
    "public_url",
    "metric",
    "command_output",
    "screenshot",
    "meeting_note",
    "policy",
    "redacted_source",
    "other",
}
ENTRY_REQUIRED = ("id", "item", "source_type", "source", "provenance", "handling")
DOCUMENT_REQUIRED = (
    "schema_version",
    "ledger_id",
    "decision",
    "prepared_by",
    "freeze_time_utc",
    "ledger_status",
    "sensitivity",
    "entries",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_ledger_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("ledger root must be a JSON object")
    return data


def write_ledger_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def validate_ledger_document(data: Any, *, require_entries: bool = True) -> list[str]:
    failures: list[str] = []
    if not isinstance(data, dict):
        return ["ledger root must be a JSON object"]

    for key in DOCUMENT_REQUIRED:
        if key not in data:
            failures.append(f"missing required field {key}")

    if data.get("schema_version") != SCHEMA_VERSION:
        failures.append(f"schema_version must be {SCHEMA_VERSION}")
    if not non_empty_string(data.get("ledger_id")):
        failures.append("ledger_id must be a non-empty string")
    if not non_empty_string(data.get("decision")):
        failures.append("decision must be a non-empty string")
    if not non_empty_string(data.get("prepared_by")):
        failures.append("prepared_by must be a non-empty string")
    if not valid_utc_timestamp(data.get("freeze_time_utc")):
        failures.append("freeze_time_utc must use YYYY-MM-DDTHH:MM:SSZ")
    if data.get("ledger_status") not in LEDGER_STATUS_VALUES:
        failures.append(f"ledger_status must be one of {sorted(LEDGER_STATUS_VALUES)}")
    if data.get("sensitivity") not in SENSITIVITY_VALUES:
        failures.append(f"sensitivity must be one of {sorted(SENSITIVITY_VALUES)}")

    entries = data.get("entries")
    if not isinstance(entries, list):
        failures.append("entries must be an array")
        return failures
    if require_entries and not entries:
        failures.append("entries must not be empty")

    seen: set[str] = set()
    for index, entry in enumerate(entries):
        location = f"entries[{index}]"
        if not isinstance(entry, dict):
            failures.append(f"{location} must be an object")
            continue
        for key in ENTRY_REQUIRED:
            if not non_empty_string(entry.get(key)):
                failures.append(f"{location}.{key} must be a non-empty string")
        entry_id = entry.get("id")
        if isinstance(entry_id, str) and not LEDGER_ID_RE.match(entry_id):
            failures.append(f"{location}.id must match E<number>")
        if isinstance(entry_id, str) and entry_id in seen:
            failures.append(f"duplicate evidence id {entry_id}")
        if isinstance(entry_id, str) and LEDGER_ID_RE.match(entry_id):
            number = int(entry_id[1:])
            expected = index + 1
            if number != expected:
                failures.append(f"{location}.id must be contiguous starting at E1")
            seen.add(entry_id)
        if entry.get("source_type") not in SOURCE_TYPE_VALUES:
            failures.append(f"{location}.source_type must be one of {sorted(SOURCE_TYPE_VALUES)}")
        if "post_freeze" in entry and not isinstance(entry["post_freeze"], bool):
            failures.append(f"{location}.post_freeze must be boolean when present")
        if "content_hash" in entry and not valid_content_hash(entry["content_hash"]):
            failures.append(f"{location}.content_hash must look like sha256:<hex>")

    validate_gap_array(data, "open_evidence_gaps", failures)
    validate_redaction_array(data, failures)
    return failures


def ledger_document(
    *,
    ledger_id: str,
    decision: str,
    prepared_by: str,
    freeze_time_utc: str,
    sensitivity: str,
    entries: list[dict[str, Any]],
    ledger_status: str = "frozen",
    open_evidence_gaps: list[dict[str, str]] | None = None,
    redactions: list[dict[str, str]] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ledger_id": ledger_id,
        "decision": decision,
        "prepared_by": prepared_by,
        "freeze_time_utc": freeze_time_utc,
        "ledger_status": ledger_status,
        "sensitivity": sensitivity,
        "entries": entries,
        "open_evidence_gaps": open_evidence_gaps or [],
        "redactions": redactions or [],
    }
    if notes:
        document["notes"] = notes
    return document


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def valid_content_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"sha256:[0-9a-fA-F]{16,64}", value))


def validate_gap_array(data: dict[str, Any], key: str, failures: list[str]) -> None:
    value = data.get(key, [])
    if not isinstance(value, list):
        failures.append(f"{key} must be an array when present")
        return
    for index, item in enumerate(value):
        location = f"{key}[{index}]"
        if not isinstance(item, dict):
            failures.append(f"{location} must be an object")
            continue
        if not non_empty_string(item.get("claim")):
            failures.append(f"{location}.claim must be a non-empty string")
        if not non_empty_string(item.get("would_be_settled_by")):
            failures.append(f"{location}.would_be_settled_by must be a non-empty string")


def validate_redaction_array(data: dict[str, Any], failures: list[str]) -> None:
    value = data.get("redactions", [])
    if not isinstance(value, list):
        failures.append("redactions must be an array when present")
        return
    for index, item in enumerate(value):
        location = f"redactions[{index}]"
        if not isinstance(item, dict):
            failures.append(f"{location} must be an object")
            continue
        for key in ("description", "reason", "confidence_impact"):
            if not non_empty_string(item.get(key)):
                failures.append(f"{location}.{key} must be a non-empty string")
