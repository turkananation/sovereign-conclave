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

import base64
import json
import os
import re
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
    make_appeal,
    make_dissent,
    make_evidence_ledger,
    make_manifest,
    make_panel,
    make_persona,
    make_protocol_params,
    make_question,
    make_round,
    make_summary,
    make_telemetry,
    make_turn,
    make_verdict,
    raw_cid,
)
from conclave_core.appeals import DEFAULT_WEIGHT_SHARE_MICRO, weight_share_micro
from conclave_core.mldsa import public_fingerprint, public_key_bytes
from conclave_core.merkle import consistency_proof, path, tree_hash
from conclave_core.cid import Cid, parse
from conclave_core.keystore import IDENTITY_SEED_FILE, REGISTRY_SEED_FILE, load_or_create_seed
from conclave_core.signing import (
    DOMAIN_DISSENT_FILING,
    DOMAIN_PERSONA_MANIFEST,
    DOMAIN_ROUND_ATTESTATION,
    DOMAIN_VERDICT,
    DOMAIN_APPEAL_PETITION,
    make_certificate_signed,
    make_key_publication_signed,
    make_signature_signed,
    make_signed_tree_head_signed,
)
from provider_runner import parse_consensus, parse_distillation

BUNDLE_VERSION = 1
LOG_ID = "conclave-log"

__all__ = [
    "BUNDLE_VERSION",
    "LOG_ID",
    "CaseSeed",
    "append_artifacts_to_bundle",
    "emit_case_bundle",
    "supplement_ledger_artifact",
]


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


def _externals_for(record: dict) -> tuple[bytes, bytes]:
    prompt = str(record.get("prompt", "")).encode("utf-8")
    output = str(record.get("response", "")).encode("utf-8")
    return prompt, output


def _extract_confidence(text: str) -> str:
    """Mechanical confidence parse; unparseable text stays conservative (low)."""

    match = re.search(r"confidence\s*[:\-=]?\s*(low|medium|high)", text, re.IGNORECASE)
    return match.group(1).lower() if match else "low"


def _deliberation_artifacts(
    case: CaseSeed,
    persona_by_seat: dict[str, Any],
    convened: list[str],
) -> tuple[list[dict], list[tuple[str, bytes]], list[Any], dict]:
    """Build the provider-run artifact set from the transcript.

    Returns ``(artifacts, externals, round_cids, verdict_inputs)``. Each
    transcript round index becomes one Round artifact with its seat Turn
    artifacts; the mechanical distill pass produces that round's Summary
    artifact, and every call (seat and mechanical alike) gets a Telemetry
    artifact over the artifact it produced: turns for seats, the Summary for
    distillation, the Round for consensus scoring and for the synthesizer.
    Prompt and output bytes land as ``<cid>.raw`` payloads so every
    input-context CID resolves offline.

    ``verdict_inputs`` carries the M5 verdict chain's raw materials: the
    synthesizer's text, the marshall verification turn CID, the final
    consensus payload, and each seat's final recorded response/turn pair.
    """

    records = [record for record in case.transcript or []]
    turn_by_key: dict[int, dict] = {}
    turn_cid_by_key: dict[int, Any] = {}
    round_meta: dict[int, dict] = {}
    speaking_keys_by_round: dict[int, list[int]] = {}
    all_keys_by_round: dict[int, list[int]] = {}
    externals: list[tuple[str, bytes]] = []

    seat_final: dict[str, dict[str, Any]] = {}
    synthesis_text = ""
    verification_turn_cid: Any = None

    for record in records:
        round_index = max(0, int(record.get("round", 0) or 0))
        meta = round_meta.setdefault(
            round_index,
            {
                "kind": str(record.get("roundKind", "opening")),
                "summary": None,
                "summary_error": None,
                "consensus": None,
                "consensus_error": None,
                "distill_model": "",
            },
        )
        role = record.get("role")
        seat_id = record.get("seat")

        if role in ("distill", "consensus"):
            if role == "distill":
                meta["distill_model"] = str(record.get("model_family", ""))
                parsed = parse_distillation(str(record.get("response", "")))
                if parsed is None:
                    meta["summary_error"] = (
                        "mechanical distillation failed to produce a valid record; "
                        "the round falls back to verbatim positions"
                    )
                else:
                    meta["summary"] = parsed
            else:
                meta["consensus"] = parse_consensus(str(record.get("response", "")))
                if meta["consensus"] is None:
                    meta["consensus_error"] = "consensus scoring failed to produce a valid score"
            continue

        if seat_id not in persona_by_seat:
            continue  # the synthesizer is presentation, not a seat turn

        prompt, output = _externals_for(record)
        prompt_cid = raw_cid(prompt)
        output_cid = raw_cid(output)
        key = id(record)
        turn = make_turn(
            round_index=round_index,
            seat_id=seat_id,
            persona=persona_by_seat[seat_id],
            input_context_hash=prompt_cid,
            model_id=str(record.get("model_family", "")),
            output=output_cid,
            citations=[],
            recorded_at=case.timestamp,
            provider_run=True,
            note=f"provider slot={record.get('slot')} provider={record.get('provider')} role={role}",
        )
        turn_by_key[key] = turn
        turn_cid_by_key[key] = artifact_cid(turn)
        externals.append((f"{prompt_cid}.raw", prompt))
        externals.append((f"{output_cid}.raw", output))
        if role == "round":
            speaking_keys_by_round.setdefault(round_index, []).append(key)
            seat_final[seat_id] = {"text": str(record.get("response", "")), "turn_cid": turn_cid_by_key[key]}
        elif role == "verification":
            verification_turn_cid = turn_cid_by_key[key]
        all_keys_by_round.setdefault(round_index, []).append(key)
        if role == "synthesis":
            synthesis_text = str(record.get("response", ""))

    summary_cid_by_round: dict[int, Any] = {}
    round_cids: list[Any] = []
    artifacts: list[dict] = []

    for round_index in sorted(round_meta):
        meta = round_meta[round_index]
        speaking_cids = [turn_cid_by_key[key] for key in speaking_keys_by_round.get(round_index, [])]
        all_turn_cids = [turn_cid_by_key[key] for key in all_keys_by_round.get(round_index, [])]

        if meta["summary"] is not None and speaking_cids:
            summary_text = meta["summary"]["summaryText"]
            summary = make_summary(
                round_index=round_index,
                distilled_from=speaking_cids,
                positions=meta["summary"]["positions"],
                summary_text=summary_text,
                open_disagreements=meta["summary"].get("openDisagreements", []),
                written_at=case.timestamp,
                model_id=meta["distill_model"] or None,
                word_count=len(summary_text.split()) or None,
            )
            summary_cid_by_round[round_index] = artifact_cid(summary)
            artifacts.append(summary)

        round_artifact = make_round(
            index=round_index,
            prev=round_cids[-1] if round_cids else None,
            status="committed",
            participants=convened,
            turns=all_turn_cids or None,
            distilled_summary=summary_cid_by_round.get(round_index),
            no_distillation_reason=(
                None
                if summary_cid_by_round.get(round_index) is not None
                else (meta["summary_error"] or "no distillation pass for this round")
            ),
            round_kind=meta["kind"],
            opened_at=case.timestamp,
            closed_at=case.timestamp,
        )
        artifacts.append(round_artifact)
        round_cids.append(artifact_cid(round_artifact))
        artifacts.extend(turn_by_key[key] for key in all_keys_by_round.get(round_index, []))

    for record in records:
        role = record.get("role")
        round_index = max(0, int(record.get("round", 0) or 0))
        key = id(record)
        if key in turn_cid_by_key:
            subject, subject_kind = turn_cid_by_key[key], "turn"
        elif role == "distill" and summary_cid_by_round.get(round_index) is not None:
            subject, subject_kind = summary_cid_by_round[round_index], "summary"
        else:
            subject, subject_kind = round_cids[round_index], "round"

        meta = round_meta[round_index]
        usage = record.get("usage")
        if usage is None:
            estimated = True
            prompt_source = record.get("prompt_chars")
            input_tokens = (
                int(prompt_source) if prompt_source is not None else len(str(record.get("prompt", "")))
            ) // 4
            token_block = {
                "inputTokens": input_tokens,
                "outputTokens": len(str(record.get("response", ""))) // 4,
            }
        else:
            estimated = False
            token_block = {
                "inputTokens": int(usage.get("inputTokens", 0) or 0),
                "outputTokens": int(usage.get("outputTokens", 0) or 0),
                "cacheReadTokens": int(usage.get("cacheReadTokens", 0) or 0),
                "cacheWriteTokens": int(usage.get("cacheWriteTokens", 0) or 0),
            }
        parts = record.get("prompt_parts")
        input_parts = (
            {
                "staticChars": int(parts.get("static", 0)),
                "dynamicChars": int(parts.get("dynamic", 0)),
                "suffixChars": int(parts.get("suffix", 0)),
            }
            if parts
            else None
        )

        notes = []
        if role == "consensus":
            if meta["consensus"] is not None:
                dissent = ", ".join(meta["consensus"]["activeDissent"]) or "none"
                notes.append(f"consensusScore={meta['consensus']['consensusScore']}; activeDissent={dissent}")
            else:
                notes.append(meta["consensus_error"] or "consensus unparseable")
        if not record.get("ok", False):
            notes.append("provider call failed; usage estimates are unreliable")
        telemetry = make_telemetry(
            subject=subject,
            subject_kind=subject_kind,
            tokens=token_block,
            model_id=str(record.get("model_family", "")),
            provider=str(record.get("provider", "")),
            latency_ms=int(round(float(record.get("elapsed_s", 0.0)) * 1000)),
            estimated=estimated,
            batch=bool(record.get("batch", False)),
            input_parts=input_parts,
            recorded_at=case.timestamp,
            note="; ".join(notes) or None,
        )
        artifacts.append(telemetry)

    final_index = max(round_meta) if round_meta else 0
    final_meta = round_meta.get(final_index, {})
    verdict_inputs = {
        "synthesis": synthesis_text,
        "verification_turn_cid": verification_turn_cid,
        "final_consensus": final_meta.get("consensus"),
        "seat_final": seat_final,
    }
    return artifacts, externals, round_cids, verdict_inputs


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
    provider_round_cids: list[Any] = []
    verdict_inputs: dict | None = None
    if case.transcript:
        persona_by_seat = {seat_id: artifact_cid(personas[seat_id]) for seat_id in convened}
        provider_artifacts, externals, provider_round_cids, verdict_inputs = _deliberation_artifacts(
            case, persona_by_seat, convened
        )
        artifacts.extend(provider_artifacts)
        manifest_rounds = make_manifest(
            case_id=case_id,
            question=artifact_cid(question),
            evidence_ledger=artifact_cid(ledger),
            panel=artifact_cid(panel),
            protocol_params=artifact_cid(params),
            rounds=provider_round_cids,
            supersedes=artifact_cid(manifest_open),
            title=case.problem or "Untitled conclave case",
            opened_at=case.timestamp,
        )
        case_manifest = manifest_rounds
        artifacts.append(manifest_rounds)

    # ---- M5 verdict issuance (rounds -> verdict -> final manifest) ---------
    advocacy_seats = [seat_id for seat_id in convened if seat_lookup[seat_id].get("type") == "advocate"]
    persona_by_seat = {seat_id: artifact_cid(personas[seat_id]) for seat_id in convened}

    if not provider_round_cids:
        scaffold_round = make_round(
            index=0,
            prev=None,
            status="committed",
            participants=convened,
            turns=None,
            no_distillation_reason=(
                "scaffold run: deterministic form validation only; no provider calls occurred"
            ),
            round_kind="scaffold",
            opened_at=case.timestamp,
            closed_at=case.timestamp,
        )
        artifacts.append(scaffold_round)
        provider_round_cids = [artifact_cid(scaffold_round)]

    votes: list[dict] = []
    dissent_cids: list[Any] = []
    confidence = "low"
    dissent_note = None
    dissent_seats: list[str] = []
    if verdict_inputs is not None:
        synthesis_text = verdict_inputs["synthesis"]
        confidence = _extract_confidence(synthesis_text)
        for seat_id in advocacy_seats:
            final = verdict_inputs["seat_final"].get(seat_id)
            if final:
                votes.append(
                    {
                        "seatId": seat_id,
                        "persona": persona_by_seat[seat_id],
                        "stance": final["text"][:160],
                        "weightMicro": 1_000_000,
                    }
                )
        active_dissent = (verdict_inputs["final_consensus"] or {}).get("activeDissent", [])
        dissent_seats = [seat_id for seat_id in active_dissent if seat_id in advocacy_seats]
        for seat_id in dissent_seats:
            final = verdict_inputs["seat_final"].get(seat_id)
            grounds = final["text"][:600] if final else "dissent classified by the mechanical consensus scorer"
            cited_ledger_ids = sorted(set(re.findall(r"E\d+", grounds)))
            dissent = make_dissent(
                round_cid=provider_round_cids[-1],
                seat_id=seat_id,
                persona=persona_by_seat[seat_id],
                grounds=grounds,
                cited_ledger_ids=cited_ledger_ids,
                cited_turns=[final["turn_cid"]] if final else None,
                filed_at=case.timestamp,
            )
            artifacts.append(dissent)
            artifacts.append(
                make_signature_signed(
                    seed=orchestrator_seed,
                    domain=DOMAIN_DISSENT_FILING,
                    payload=artifact_cid(dissent),
                    signed_at=case.timestamp,
                )
            )
            dissent_cids.append(artifact_cid(dissent))
    if dissent_cids:
        dissent_note = (
            "active dissent auto-classified by the final consensus scorer; dissents "
            f"recorded as artifacts for seats: {', '.join(dissent_seats)}"
        )

    if verdict_inputs is not None and verdict_inputs["synthesis"].strip():
        synthesis_text = verdict_inputs["synthesis"]
        if synthesis_text.lower().startswith("the sovereign conclave advises"):
            recommendation = synthesis_text
            verdict_note = None
        else:
            recommendation = "The Sovereign Conclave advises: " + synthesis_text.strip()
            verdict_note = (
                "recommendation envelope: mechanical protocol prefix applied to the "
                "synthesizer's advice; seat stances truncated to 160 characters"
            )
    else:
        recommendation = (
            "The Sovereign Conclave advises: the scaffold validates form only; "
            "a seated deliberation is required before this question is decided."
        )
        verdict_note = "scaffold run: no provider calls; standing scaffold advice"

    verdict = make_verdict(
        manifest=artifact_cid(case_manifest),
        final_round=provider_round_cids[-1],
        decision=case.problem or "Untitled conclave case",
        recommendation=recommendation,
        votes=votes,
        confidence=confidence,
        dissents=dissent_cids or None,
        marshall_verification=verdict_inputs["verification_turn_cid"] if verdict_inputs else None,
        dissent_recorded_note=dissent_note,
        issued_at=case.timestamp,
        note=verdict_note,
    )
    verdict_cid = artifact_cid(verdict)
    artifacts.append(verdict)
    artifacts.append(
        make_signature_signed(
            seed=identity_seed,
            domain=DOMAIN_VERDICT,
            payload=verdict_cid,
            signed_at=case.timestamp,
        )
    )
    manifest_final = make_manifest(
        case_id=case_id,
        question=artifact_cid(question),
        evidence_ledger=artifact_cid(ledger),
        panel=artifact_cid(panel),
        protocol_params=artifact_cid(params),
        rounds=provider_round_cids,
        verdict=verdict_cid,
        supersedes=artifact_cid(case_manifest),
        title=case.problem or "Untitled conclave case",
        opened_at=case.timestamp,
    )
    case_manifest = manifest_final
    artifacts.append(manifest_final)

    # ---- automatic T3 scheduling -------------------------------------------
    # Roadmap M5 T3: when filed dissents hold >= 30% of the voting weight,
    # appellate review is scheduled mechanically, immediately, with no gate.
    auto_t3_appeal = None
    if dissent_cids:
        dissent_store = {
            artifact_cid(artifact): artifact
            for artifact in artifacts
            if artifact.get("type") == "Dissent"
        }
        share = weight_share_micro(verdict, dissent_store.get)
        if share is not None and share >= DEFAULT_WEIGHT_SHARE_MICRO:
            auto_t3_appeal = make_appeal(
                verdict=verdict_cid,
                case_manifest=artifact_cid(case_manifest),
                trigger="T3",
                grounds=(
                    f"automatic: dissent weight share {share} micro >= "
                    f"{DEFAULT_WEIGHT_SHARE_MICRO} threshold at verdict issuance"
                ),
                filed_by="mechanical:T3",
                filed_at=case.timestamp,
                window_days=int(params.get("appealDefaultWindowDays", 30)),
            )
            artifacts.append(auto_t3_appeal)
            artifacts.append(
                make_signature_signed(
                    seed=orchestrator_seed,
                    domain=DOMAIN_APPEAL_PETITION,
                    payload=artifact_cid(auto_t3_appeal),
                    signed_at=case.timestamp,
                )
            )
            auto_t3_cid = artifact_cid(auto_t3_appeal)

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
    for round_cid in provider_round_cids:
        artifacts.append(
            make_signature_signed(
                seed=orchestrator_seed,
                domain=DOMAIN_ROUND_ATTESTATION,
                payload=round_cid,
                signed_at=case.timestamp,
            )
        )

    # ---- transparency log checkpoint --------------------------------------
    # The opening checkpoint is an empty tree; a closing verdict appends its
    # CID as leaf 0 with an identity signature and an extended tree head.
    sth, sth_signature = make_signed_tree_head_signed(
        log_id=LOG_ID,
        tree_size=0,
        root_hash=tree_hash([]),
        seed=identity_seed,
        published_at=case.timestamp,
    )
    artifacts += [sth, sth_signature]
    log_section = {
        "leaves": [],
        "sthCids": [str(artifact_cid(sth))],
        "consistency": [],
        "inclusion": {},
    }
    if verdict is not None:
        leaf_cids = [verdict_cid]
        if auto_t3_appeal is not None:
            leaf_cids.append(artifact_cid(auto_t3_appeal))
        total_leaves = len(leaf_cids)
        for size in range(1, total_leaves + 1):
            root = tree_hash([leaf.cid_bytes() for leaf in leaf_cids[:size]])
            sth_growth, sth_growth_signature = make_signed_tree_head_signed(
                log_id=LOG_ID,
                tree_size=size,
                root_hash=root,
                seed=identity_seed,
                published_at=case.timestamp,
            )
            artifacts += [sth_growth, sth_growth_signature]
            log_section["sthCids"].append(str(artifact_cid(sth_growth)))
            if size > 1:
                log_section["consistency"].append(
                    {
                        "first": size - 1,
                        "second": size,
                        "path": _encode_nodes(
                            consistency_proof(size - 1, [leaf.cid_bytes() for leaf in leaf_cids[:size]])
                        ),
                    }
                )
        log_section["leaves"] = [str(leaf) for leaf in leaf_cids]
        for index, leaf in enumerate(leaf_cids):
            log_section["inclusion"][str(leaf)] = {
                "index": index,
                "treeSize": total_leaves,
                "path": _encode_nodes(path(index, [leaf.cid_bytes() for leaf in leaf_cids])),
            }

    _write_bundle_files(bundle_dir, artifacts, externals)
    config = {
        "version": BUNDLE_VERSION,
        "manifestCid": str(artifact_cid(case_manifest)),
        "expectedIdentityFingerprint": public_fingerprint(identity_public),
        "expectedRegistryFingerprint": public_fingerprint(registry_public),
        "log": log_section,
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


def _encode_nodes(nodes: list[bytes]) -> list[str]:
    return [base64.b64encode(node).decode("ascii") for node in nodes]


LOGGED_TYPES = (
    "Verdict", "Dissent", "EvidenceLedger", "Appeal",
    "AppealScreening", "AppealVerdict", "ArbiterRuling",
)


def supplement_ledger_artifact(
    engine: Any,
    document_entries: list[dict[str, Any]],
    created_at: str,
) -> dict:
    """T1 supplement: a new EvidenceLedger carrying ALL frozen entries plus the
    supplement's, with IDs continuing E1..E{n+k} and ``supersedes`` chaining
    back to the frozen ledger artifact. The frozen ledger's CID is preserved
    via the chain; the manifest itself is never rewritten.
    """

    ledger_cid = engine.manifest["evidenceLedger"]
    stored = engine.store.get(ledger_cid)
    if not isinstance(stored, dict):
        raise SystemExit(f"the bundle's frozen evidence ledger {ledger_cid} is missing")
    entries = list(stored["entries"])
    index = len(entries) + 1
    for entry in document_entries:
        artifact_entry: dict[str, Any] = {
            "id": f"E{index}",
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
        index += 1
    return make_evidence_ledger(entries, supersedes=ledger_cid, created_at=created_at)


def append_artifacts_to_bundle(
    bundle_dir: Path,
    artifacts: list[dict],
    *,
    identity_seed: bytes,
    published_at: str,
) -> dict:
    """Append appeal-lifecycle artifacts to an emitted bundle.

    Writes every artifact file, extends the transparency log with one leaf
    per logged lifecycle document (verdicts, dissents, appeals, screenings,
    appellate verdicts, arbiter rulings), adds a signed tree head per growth
    step with an RFC 6962 consistency proof against the prior head, records
    inclusion proofs for the new leaves, and rewrites bundle.json. The
    existing artifact set and the manifest chain are never modified; appeal
    artifacts reference the manifest rather than superseding it.

    Returns the rewritten bundle config.
    """

    bundle_dir = Path(bundle_dir)
    config = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    log_section = config["log"]
    old_leaves = [parse(entry) for entry in log_section["leaves"]]
    prior_size = len(old_leaves)

    _write_bundle_files(bundle_dir, artifacts, [])

    leaves = list(old_leaves)
    for artifact in artifacts:
        if artifact.get("type") in LOGGED_TYPES:
            leaves.append(artifact_cid(artifact))
    log_section["leaves"] = [str(leaf) for leaf in leaves]

    final_new = []
    for size in range(prior_size + 1, len(leaves) + 1):
        root = tree_hash([leaf.cid_bytes() for leaf in leaves[:size]])
        sth, sth_signature = make_signed_tree_head_signed(
            log_id=LOG_ID,
            tree_size=size,
            root_hash=root,
            seed=identity_seed,
            published_at=published_at,
        )
        final_new += [sth, sth_signature]
        log_section["sthCids"].append(str(artifact_cid(sth)))
        if prior_size > 0:
            log_section["consistency"].append(
                {
                    "first": prior_size,
                    "second": size,
                    "path": _encode_nodes(
                        consistency_proof(prior_size, [leaf.cid_bytes() for leaf in leaves[:size]])
                    ),
                }
            )
    _write_bundle_files(bundle_dir, final_new, [])

    for index, leaf in enumerate(leaves[prior_size:], start=prior_size):
        log_section["inclusion"][str(leaf)] = {
            "index": index,
            "treeSize": len(leaves),
            "path": _encode_nodes(path(index, [leaf.cid_bytes() for leaf in leaves])),
        }

    (bundle_dir / "bundle.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return config


if __name__ == "__main__":
    raise SystemExit(
        "artifact_emitter is a library module; run it via bin/conclave --write-bundle"
    )
