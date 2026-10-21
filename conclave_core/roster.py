"""Persona artifact construction from roster seat definitions.

Shared by the bundle emitter and the server orchestrator so a convened seat
is described identically in both paths. A roster seat dict carries at least
``id`` and ``model`` plus its descriptive fields (``type``, ``tier``,
``lens``, ``display_name``, optional ``path`` to the persona's roster
document). The resolver never reads files unless a ``root`` is supplied.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import make_persona, raw_cid


def persona_for_seat(
    seat: dict[str, Any],
    roster_version: str,
    *,
    agent_markdown: dict[str, Path] | None = None,
    root: Path | None = None,
) -> dict:
    """Build the Persona artifact for one roster seat."""

    role = seat.get("type", "advocate")
    lens = str(seat.get("lens", "")).strip()
    persona = make_persona(
        seat_id=seat["id"],
        display_name=str(seat.get("display_name") or seat["id"]),
        tier=str(seat.get("tier", "General")),
        lens=lens or f"{role} lens",
        stance=f"Convenes as a {role} seat. Argues the {lens or 'prescribed'} lens.",
        how_you_argue=(
            [
                "Applies the roster lens for this seat.",
                "Attacks the strongest opposing claim; concedes when the ledger disagrees.",
            ]
            if role == "advocate"
            else ["Structural checks only.", "States a bound, not an option preference."]
        ),
        characteristic_bias="Full persona prose lives in the roster document (sourceDigest).",
        is_not=["Not any other seat."],
        model=str(seat.get("model", "local")),
        version=roster_version,
    )
    markdown_path = (agent_markdown or {}).get(seat["id"])
    if markdown_path is None and root is not None:
        from_path = Path(root) / seat.get("path", "")
        markdown_path = from_path if from_path.is_file() else None
    if markdown_path is not None:
        persona["sourceDigest"] = raw_cid(Path(markdown_path).read_bytes())
    return persona
