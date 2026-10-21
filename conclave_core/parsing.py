"""Structured distillation and consensus parsing (mechanical cascade tier).

Shared by the provider runner (M4 transcript parsing) and the server
orchestrator (M6 live runs): both consume the same JSON contract for
distiller and consensus-scorer responses. Parsing is total and failure
conservative — any deviation from the expected shape returns ``None`` /
``False`` rather than raising, so callers degrade gracefully.
"""

from __future__ import annotations

import json
import re


def parse_distillation(text: str) -> dict | None:
    """Extract and normalize a distiller JSON payload; None on any failure."""

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    summary_text = payload.get("summaryText")
    positions = payload.get("positions")
    if not isinstance(summary_text, str) or not summary_text.strip():
        return None
    if not isinstance(positions, list) or not positions:
        return None
    normalized_positions = []
    for position in positions:
        if not isinstance(position, dict):
            return None
        seat_id = position.get("seatId")
        stance = position.get("stance")
        if not isinstance(seat_id, str) or not seat_id or not isinstance(stance, str) or not stance.strip():
            return None
        raw_citations = position.get("citations", [])
        citations = [str(item) for item in raw_citations] if isinstance(raw_citations, list) else []
        normalized_positions.append({"seatId": seat_id, "stance": stance.strip(), "citations": citations})
    disagreements = payload.get("openDisagreements", [])
    disagreements = [str(item) for item in disagreements] if isinstance(disagreements, list) else []
    return {
        "summaryText": summary_text.strip(),
        "positions": normalized_positions,
        "openDisagreements": disagreements,
    }


def parse_consensus(text: str) -> dict | None:
    """Extract and normalize a consensus JSON payload; None on any failure."""

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    score = payload.get("consensusScore")
    if not isinstance(score, int) or isinstance(score, bool):
        return None
    dissent = payload.get("activeDissent", [])
    dissent = [str(seat) for seat in dissent] if isinstance(dissent, list) else []
    return {"consensusScore": max(0, min(100, score)), "activeDissent": dissent}


def consensus_reached(consensus: dict | None, threshold: int) -> bool:
    """Early-exit gate: score at/above threshold with no active dissent."""

    return (
        consensus is not None
        and consensus["consensusScore"] >= threshold
        and not consensus["activeDissent"]
    )
