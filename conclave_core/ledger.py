"""Evidence-ledger draft normalization.

The convene path drafts ledger entries in document shape (``item`` prose in
object form); cases freeze those drafts into the artifact entry shape the
EvidenceLedger stores. Both the bundle emitter and the server orchestrator
freeze drafts through this module so entry shapes cannot drift apart.
"""

from __future__ import annotations

from typing import Any

from .artifacts import make_evidence_ledger
from .cid import Cid


def artifact_ledger_entry(draft: dict[str, Any], entry_id: str) -> dict[str, Any]:
    """Freeze one ledger draft entry into artifact entry shape."""

    entry: dict[str, Any] = {
        "id": entry_id,
        "item": str(draft.get("item", "")),
        "provenance": {
            "source": str(draft.get("source", "")),
            "kind": str(draft.get("source_type", "imported")),
        },
        "handling": str(draft.get("handling", "")),
    }
    if draft.get("sensitivity"):
        entry["sensitivity"] = str(draft["sensitivity"])
    return entry


def artifact_entries_from_draft(drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Freeze a full draft in order.

    A draft's own ``id`` stands when supplied (the emitter fixture path);
    otherwise IDs continue E1..E{n} (the supplement path).
    """

    entries: list[dict[str, Any]] = []
    next_index = 1
    for draft in drafts:
        if draft.get("id") is not None:
            entry_id = str(draft["id"])
        else:
            entry_id = f"E{next_index}"
            next_index += 1
        entries.append(artifact_ledger_entry(draft, entry_id))
    return entries


def supplement_ledger(
    frozen_ledger: dict[str, Any], frozen_ledger_cid: Cid, drafts: list[dict[str, Any]]
) -> dict[str, Any]:
    """T1 supplement: ALL frozen entries plus the new documents as a new
    EvidenceLedger whose IDs continue E1..E{n+k} and whose ``supersedes``
    chains back to the frozen ledger artifact. The frozen ledger's CID is
    preserved via the chain; the manifest itself is never rewritten.
    """

    entries = list(frozen_ledger.get("entries", []))
    start = len(entries)
    for offset, draft in enumerate(drafts, start=0):
        entries.append(artifact_ledger_entry(draft, f"E{start + offset + 1}"))
    return make_evidence_ledger(entries, supersedes=frozen_ledger_cid)
