#!/usr/bin/env python3
"""Emit a Sovereign Conclave case as a v0.2 artifact bundle (M3).

A case bundle is the verifiable artifact form of a conclave run:
content-addressed DAG-CBOR artifacts plus ML-DSA-65 signatures and the
RFC 6962 log checkpoint — everything the offline verifier needs. The
scaffold (offline) run emits an *opening case*: manifest, evidence
ledger, personas, panel, protocol params, and the key/certificate
chain, with an empty transparency log. An opt-in provider run
additionally records every seat call as a Turn artifact whose CIDs
reference the exact prompt and output bytes (stored alongside as
``<cid>.raw``), one committed Round, and an orchestrator attestation.

Bundle layout (what ``conclave_core.verifier`` reads):

    bundle/
      artifacts/<cid>.cbor   canonical DAG-CBOR artifact bytes
      artifacts/<cid>.raw    raw prompt/output bytes referenced by Turn CIDs
      bundle.json            case pointer + trust config + log section

Keys live in the keystore directory (default ``~/.conclave/keys``):
``identity.seed`` (long-lived: verdict signer, log signer, trust anchor)
and ``registry.seed`` (persona registry). The orchestrator key is minted
fresh per case and certified by the identity key inside the bundle.

This module is a library; run it through ``bin/conclave --write-bundle``.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conclave_core.artifacts import (
    ArtifactError,
    artifact_bytes,
    artifact_cid,
    make_evidence_ledger,
    make_manifest,
    make_panel,
    make_persona,
    make_protocol_params,
    make_question,
    make_round,
    make_turn,
    raw_cid,
)
from conclave_core.mldsa import public_fingerprint, public_key_bytes
from conclave_core.merkle import tree_hash
from conclave_core.keystore import IDENTITY_SEED_FILE, REGISTRY_SEED_FILE, load_or_create_seed
from conclave_core.signing import (
    DOMAIN_PERSONA_MANIFEST,
    DOMAIN_ROUND_ATTESTATION,
    make_certificate_signed,
    make_key_publication_signed,
    make_signature_signed,
    make_signed_tree_head_signed,
)

BUNDLE_VERSION = 1
LOG_ID = "conclave-log"

__all__ = ["BUNDLE_VERSION", "LOG_ID", "CaseSeed", "emit_case_bundle"]


@dataclass
class CaseSeed:
    """Everything the emitter needs about one conclave invocation."""

    profile_id: str
    problem: str
    timestamp: str
    seats: list[str]
    marshall_id: str
    roster: dict[str, Any]
    ledger_entries: list[dict[str, Any]]
    transcript: list[dict[str, Any]] | None = None   # provider records with prompt + response
    agent_markdown: dict[str, Path] | None = None    # seatId -> agent document path


def _persona_artifact(seat: dict[str, Any], roster_version: str, case: CaseSeed) -> dict:
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
    markdown_path = (case.agent_markdown or {}).get(seat["id"])
    if markdown_path is None:
        from_path = ROOT / seat.get("path", "")
        markdown_path = from_path if from_path.is_file() else None
    if markdown_path is not None:
        persona["sourceDigest"] = raw_cid(markdown_path.read_bytes())
    return persona


def _ledger_artifact_entries(case: CaseSeed) -> list[dict[str, Any]]:
    entries = []
    for entry in case.ledger_entries:
        artifact_entry: dict[str, Any] = {
            "id": str(entry["id"]),
            "item": str(entry.get("item", "")),
            "provenance": {
                "source": str(entry.get("source", "")),
                "kind": str(entry.get("source_type", "imported")),
            },
            "handling": str(entry.get("handling", "")),
        }
        if entry.get("sensitivity"):
            artifact_entry["sensitivity"] = str(entry["sensitivity"])
        entries.append(artifact_entry)
    return entries


def _turn_artifacts(
    case: CaseSeed, persona_by_seat: dict[str, Any]
) -> tuple[list[dict], list[tuple[str, bytes]]]:
    """Build the Round-0 Turn artifacts from provider transcript records.

    The synthesis call is presentation, not a seat turn, and stays in the
    markdown transcript. Each turn's input/output CIDs reference raw
    bytes, returned as ``<cid>.raw`` payloads so the bundle is verifiable
    without trusting the emitter's word about what was prompted.
    """

    turns: list[dict] = []
    externals: list[tuple[str, bytes]] = []
    for record in case.transcript or []:
        if record.get("role") == "synthesis":
            continue
        seat_id = record.get("seat")
        if seat_id not in persona_by_seat:
            continue
        prompt = str(record.get("prompt", "")).encode("utf-8")
        output = str(record.get("response", "")).encode("utf-8")
        prompt_cid = raw_cid(prompt)
        output_cid = raw_cid(output)
        externals.append((f"{prompt_cid}.raw", prompt))
        externals.append((f"{output_cid}.raw", output))
        turns.append(
            make_turn(
                round_index=0,
                seat_id=seat_id,
                persona=persona_by_seat[seat_id],
                input_context_hash=prompt_cid,
                model_id=str(record.get("model_family", "")),
                output=output_cid,
                citations=[],
                recorded_at=case.timestamp,
                provider_run=True,
                note=f"provider slot={record.get('slot')} provider={record.get('provider')}",
            )
        )
    return turns, externals


def emit_case_bundle(case: CaseSeed, bundle_dir: Path, keys_dir: Path) -> tuple[Path, str]:
    """Write the verifiable case bundle. Returns ``(bundle_dir, identity_fingerprint)``."""

    bundle_dir = Path(bundle_dir)
    keys_dir = Path(keys_dir)
    roster = case.roster
    seat_lookup = {seat["id"]: seat for seat in roster["seats"]}
    convened = case.seats + [case.marshall_id]
    missing = [seat_id for seat_id in convened if seat_id not in seat_lookup]
    if missing:
        raise SystemExit(f"Unknown seat(s) for artifact emission: {', '.join(missing)}")

    identity_seed = load_or_create_seed(keys_dir / IDENTITY_SEED_FILE)
    registry_seed = load_or_create_seed(keys_dir / REGISTRY_SEED_FILE)
    orchestrator_seed = os.urandom(32)

    identity_public = public_key_bytes(identity_seed)
    registry_public = public_key_bytes(registry_seed)
    case_id = f"case-{case.timestamp.replace(':', '').replace('-', '')}"

    # ---- case DAG ----------------------------------------------------------
    question = make_question(
        case.problem or "<State the decision question.>",
        asked_by=case.profile_id,
        asked_at=case.timestamp,
    )
    ledger = make_evidence_ledger(_ledger_artifact_entries(case), created_at=case.timestamp)
    personas = {
        seat_id: _persona_artifact(seat_lookup[seat_id], roster["version"], case)
        for seat_id in convened
    }
    panel = make_panel(
        [
            {
                "seatId": seat_id,
                "persona": artifact_cid(personas[seat_id]),
                "model": seat_lookup[seat_id]["model"],
            }
            for seat_id in convened
        ],
        convened_at=case.timestamp,
        quorum=len(convened),
    )
    params = make_protocol_params(quorum=len(convened), recorded_by="session-orchestrator")
    manifest_open = make_manifest(
        case_id=case_id,
        question=artifact_cid(question),
        evidence_ledger=artifact_cid(ledger),
        panel=artifact_cid(panel),
        protocol_params=artifact_cid(params),
        title=case.problem or "Untitled conclave case",
        opened_at=case.timestamp,
    )
    artifacts: list[dict] = [
        question, ledger, panel, params, *personas.values(), manifest_open
    ]

    case_manifest = manifest_open
    externals: list[tuple[str, bytes]] = []
    round_zero: dict | None = None
    if case.transcript:
        persona_by_seat = {seat_id: artifact_cid(personas[seat_id]) for seat_id in convened}
        turn_list, externals = _turn_artifacts(case, persona_by_seat)
        turn_cids = [artifact_cid(turn) for turn in turn_list]
        round_zero = make_round(
            index=0,
            prev=None,
            status="committed",
            participants=convened,
            turns=turn_cids,
            no_distillation_reason=(
                "M3 scope: verbatim provider turns recorded as artifacts; "
                "structured distillation arrives in M4."
            ),
            opened_at=case.timestamp,
            closed_at=case.timestamp,
        )
        manifest_rounds = make_manifest(
            case_id=case_id,
            question=artifact_cid(question),
            evidence_ledger=artifact_cid(ledger),
            panel=artifact_cid(panel),
            protocol_params=artifact_cid(params),
            rounds=[artifact_cid(round_zero)],
            supersedes=artifact_cid(manifest_open),
            title=case.problem or "Untitled conclave case",
            opened_at=case.timestamp,
        )
        case_manifest = manifest_rounds
        artifacts += [*turn_list, round_zero, manifest_rounds]

    # ---- key + certificate chain ------------------------------------------
    identity_kp, identity_possession = make_key_publication_signed(
        seed=identity_seed, role="identity", published_at=case.timestamp
    )
    registry_kp, registry_possession = make_key_publication_signed(
        seed=registry_seed, role="persona-registry", published_at=case.timestamp
    )
    orchestrator_kp, certificate, certificate_sig = make_certificate_signed(
        orchestrator_seed=orchestrator_seed,
        identity_seed=identity_seed,
        case_manifest=artifact_cid(manifest_open),
        issued_at=case.timestamp,
    )
    orchestrator_possession = make_signature_signed(
        seed=orchestrator_seed,
        domain="orchestrator",
        payload=artifact_cid(orchestrator_kp),
        signed_at=case.timestamp,
    )
    artifacts += [
        identity_kp, identity_possession,
        registry_kp, registry_possession,
        orchestrator_kp, orchestrator_possession,
        certificate, certificate_sig,
    ]

    for persona in personas.values():
        artifacts.append(
            make_signature_signed(
                seed=registry_seed,
                domain=DOMAIN_PERSONA_MANIFEST,
                payload=artifact_cid(persona),
                signed_at=case.timestamp,
            )
        )
    if round_zero is not None:
        artifacts.append(
            make_signature_signed(
                seed=orchestrator_seed,
                domain=DOMAIN_ROUND_ATTESTATION,
                payload=artifact_cid(round_zero),
                signed_at=case.timestamp,
            )
        )

    # ---- transparency log checkpoint --------------------------------------
    # The opening log is empty: verdict leaves are appended when a case
    # closes (M5 flow later reuses make_signed_tree_head_signed).
    sth, sth_signature = make_signed_tree_head_signed(
        log_id=LOG_ID,
        tree_size=0,
        root_hash=tree_hash([]),
        seed=identity_seed,
        published_at=case.timestamp,
    )
    artifacts += [sth, sth_signature]

    _write_bundle_files(bundle_dir, artifacts, externals)
    config = {
        "version": BUNDLE_VERSION,
        "manifestCid": str(artifact_cid(case_manifest)),
        "expectedIdentityFingerprint": public_fingerprint(identity_public),
        "expectedRegistryFingerprint": public_fingerprint(registry_public),
        "log": {
            "leaves": [],
            "sthCids": [str(artifact_cid(sth))],
            "consistency": [],
            "inclusion": {},
        },
    }
    (bundle_dir / "bundle.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return bundle_dir, public_fingerprint(identity_public)


def _write_bundle_files(
    bundle_dir: Path, artifacts: list[dict], externals: list[tuple[str, bytes]]
) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = bundle_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    for artifact in artifacts:
        cid = artifact_cid(artifact)
        (artifacts_dir / f"{cid}.cbor").write_bytes(artifact_bytes(artifact))
    for name, payload in externals:
        (artifacts_dir / name).write_bytes(payload)


if __name__ == "__main__":
    raise SystemExit(
        "artifact_emitter is a library module; run it via bin/conclave --write-bundle"
    )
