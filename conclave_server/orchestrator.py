"""M6 orchestrator: the deliberation FSM driving one CaseRun over the store.

The server runs the same artifact-building contract as the bundle emitter
(``scripts/artifact_emitter.py``) but incrementally: each deliberation step
(open, seat turn, distill, consensus, round close, verdict) commits its
artifacts to the ``ArtifactStore``, then records the FSM row — artifacts
first, row second. A crash between the two replays the step from the fixed
case timestamp: every artifact except ``Signature`` is CID-identical on the
replay and re-ingests as a content-address no-op, while re-signed ML-DSA
signature artifacts are fresh-but-equivalent (FIPS 204 hedged signing) and
land only as untracked extras; the tracked DAG stays clean either way.

Documented deviations (v0.2.0):
- Seat calls go through a ``SeatClient`` adapter (stdlib HTTP in the wired
  server; stubs in tests). A record with ``"ok": False`` commits a failed
  turn like the provider runner does; a raised exception stops the run at
  its last clean step.
- The verdict phase is mechanical (no synthesizer call): the advice text
  receives the standing envelope over the final distilled summary, else the
  standing advice. Provider-backed synthesis stays an M7+ option.
- The token budget is a soft cap enforced by the degradation ladder between
  rounds: at each round boundary with ``tokens_used`` at/over budget, the
  next unused rung of ``DEGRADATION_LADDER`` applies once. ``batch`` flips
  subsequent calls to batch routing, ``tighten-sparse-topology`` halves the
  debating advocate seats for later rounds (all seats still vote), and
  ``early-verdict-reduced-rounds`` skips remaining rounds. Degradation is
  never silent: hub events, the session state, and the closing manifest
  note all record it.
- The per-case orchestrator signing seed is ephemeral (like the emitter)
  but persisted server-privately in the session row, so a resumed case
  keeps attesting with the certificate-bound key it opened with.
- The transparency log is case-scoped in the store (one Merkle log per
  conclave), matching the per-case bundle contract of the standalone
  verifier.
"""

from __future__ import annotations

import base64
import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from conclave_core.appeals import DEFAULT_WEIGHT_SHARE_MICRO, weight_share_micro
from conclave_core.artifacts import (
    artifact_cid,
    make_appeal,
    make_dissent,
    make_evidence_ledger,
    make_manifest,
    make_panel,
    make_protocol_params,
    make_question,
    make_round,
    make_summary,
    make_telemetry,
    make_turn,
    make_verdict,
    raw_cid,
    utc_now,
)
from conclave_core.cid import Cid, parse
from conclave_core.keystore import IDENTITY_SEED_FILE, REGISTRY_SEED_FILE, load_or_create_seed
from conclave_core.ledger import artifact_entries_from_draft
from conclave_core.merkle import tree_hash
from conclave_core.parsing import consensus_reached, parse_consensus, parse_distillation
from conclave_core.roster import persona_for_seat
from conclave_core.signing import (
    DOMAIN_APPEAL_PETITION,
    DOMAIN_DISSENT_FILING,
    DOMAIN_PERSONA_MANIFEST,
    DOMAIN_ROUND_ATTESTATION,
    DOMAIN_VERDICT,
    LOG_ID,
    make_certificate_signed,
    make_key_publication_signed,
    make_signature_signed,
    make_signed_tree_head_signed,
)

from .sessions import DEGRADATION_LADDER, SessionHub, SessionState
from .store import ArtifactStore

_STANDING_PROTOCOL_TEXT = (
    "The Sovereign Conclave convenes under Directive D-4: advise, never act.\n"
    "Norms: argue your roster lens; cite ledger items as E<n>; concede when the "
    "ledger disagrees; do not invent facts.\n"
)


class SeatClient:
    """Adapter the orchestrator drives for seat / mechanical calls.

    ``call(seat_id, role, round_index, round_kind, prompt)`` returns a record
    dict carrying at least ``response`` (str) plus telemetry metadata:
    ``model_family``, ``provider``, ``slot``, ``usage`` (iterable dict of
    ``inputTokens`` / ``outputTokens`` / ``cacheReadTokens`` /
    ``cacheWriteTokens``, or None to estimate from prompt/response sizes),
    ``elapsed_s``. A record may carry ``ok: False`` with an ``error``
    message; that commits a failed call's turn without aborting the run.
    """

    def call(self, seat_id: str, role: str, round_index: int, round_kind: str, prompt: str) -> dict:
        raise NotImplementedError("SeatClient.call must be overridden")


@dataclass
class ConveneRequest:
    """Everything the orchestrator needs to open one case."""

    profile_id: str
    problem: str
    roster: dict[str, Any]                  # {"version": ..., "seats": [...]}
    seats: list[str]
    marshall_id: str
    ledger_entries: list[dict[str, Any]]    # document-shape draft entries
    token_budget: int | None = None
    protocol_params: dict[str, Any] | None = None
    agent_markdown: dict[str, Path] | None = None
    timestamp: str | None = None


def _fresh_state() -> dict[str, Any]:
    return {
        "timestamp": None,
        "meta": {},                          # convened / advocates / tokenBudget / title
        "rounds": {},                        # round index (str) -> plan + records
        "seatFinal": {},                     # seat_id -> final speaking turn cid
        "verificationTurnCid": None,
        "roundCids": [],
        "manifestCid": None,
        "sthCids": [],
        "artifacts": [],                     # this case's ingested artifact CIDs
        "payloads": [],                      # this case's resolvable payload names
        "degraded": [],
        "orchestratorSeedB64": "",
        "verdictCid": None,
        "appealCid": None,
        "dissentCids": [],
    }


def _round_record() -> dict[str, Any]:
    return {
        "kind": None,
        "participants": [],
        "allTurns": [],
        "speakingTurns": [],
        "summaryCid": None,
        "distilled": None,                   # parsed distillation dict, else None
        "distillModel": "",
        "distillError": None,
        "distillCall": None,                 # telemetry metadata for the call
        "consensus": None,                   # parsed consensus dict, else None
        "consensusError": None,
        "consensusCall": None,
    }


def _load_json(text: str) -> Any:
    return json.loads(text)


def _phase_for(position: list) -> str:
    """Hub phase label for an FSM position."""

    head = position[0]
    if head == "ready":
        return "convened"
    if head == "round":
        return {"turn": "round", "distill": "distill", "consensus": "consensus"}.get(
            position[2], "round"
        )
    if head in ("verdict", "closed", "aborted"):
        return head
    return "convened"


def parse_cid_list(items: list[str]) -> list[Cid]:
    """CIDs carried in state JSON arrive as strings."""

    return [parse(item) for item in items]


class CaseRun:
    """One live deliberation: FSM over the store, events over the hub.

    Single writer per session: only the runner thread mutates its own
    ``SessionState`` fields; watchers read them under the hub lock.
    """

    def __init__(
        self,
        store: ArtifactStore,
        hub: SessionHub,
        keys_dir: Path,
        client: SeatClient,
        *,
        orchestrator_seed: bytes | None = None,
    ) -> None:
        self.store = store
        self.hub = hub
        self.keys_dir = Path(keys_dir)
        self.client = client
        self._fixed_orchestrator_seed = orchestrator_seed
        self._step_lock = threading.Lock()
        self.state: dict[str, Any] = _fresh_state()
        self.position: list = []
        self.case_ref: str = ""
        self.session_state: SessionState | None = None

    # -- construction ---------------------------------------------------------

    def convene(self, request: ConveneRequest) -> str:
        """Open the case: ingest DAG roots + trust chain; return the caseRef."""

        roster_seats = {seat["id"]: seat for seat in request.roster["seats"]}
        convened = list(request.seats) + [request.marshall_id]
        missing = [seat_id for seat_id in convened if seat_id not in roster_seats]
        if missing:
            raise ValueError(f"unknown seat(s) for convening: {', '.join(missing)}")
        if len(set(convened)) != len(convened):
            raise ValueError("duplicate seat in the convene draw")

        timestamp = request.timestamp or utc_now()
        compact = timestamp.replace(":", "").replace("-", "")
        case_ref = f"case-{request.profile_id}-{compact}"
        existing = self.store.session(case_ref)
        if existing and existing["position"] not in ('["closed"]', '["aborted"]'):
            raise ValueError(f"case is already active: {case_ref}")

        self.case_ref = case_ref
        identity_seed = load_or_create_seed(self.keys_dir / IDENTITY_SEED_FILE)
        registry_seed = load_or_create_seed(self.keys_dir / REGISTRY_SEED_FILE)
        # the seed is fixed for recordable demos/tests (byte-stable case
        # bundles) and random in live sessions; either way it is persisted
        # server-privately in the session row so kills/resumes replay it
        orchestrator_seed = self._fixed_orchestrator_seed or os.urandom(32)

        self.state = _fresh_state()
        self.state["timestamp"] = timestamp
        personas = {
            seat_id: persona_for_seat(
                roster_seats[seat_id],
                request.roster.get("version", "roster"),
                agent_markdown=request.agent_markdown,
            )
            for seat_id in convened
        }
        advocates = [
            seat_id for seat_id in convened
            if roster_seats[seat_id].get("type", "advocate") == "advocate"
        ]
        params = request.protocol_params or make_protocol_params(
            quorum=len(convened), recorded_by="session-orchestrator"
        )
        question = make_question(
            request.problem or "<State the decision question.>",
            asked_by=request.profile_id,
            asked_at=timestamp,
        )
        ledger = make_evidence_ledger(
            artifact_entries_from_draft(request.ledger_entries), created_at=timestamp
        )
        panel = make_panel(
            [
                {
                    "seatId": seat_id,
                    "persona": artifact_cid(personas[seat_id]),
                    "model": roster_seats[seat_id]["model"],
                }
                for seat_id in convened
            ],
            convened_at=timestamp,
            quorum=len(convened),
        )
        manifest_open = make_manifest(
            case_id=case_ref,
            question=artifact_cid(question),
            evidence_ledger=artifact_cid(ledger),
            panel=artifact_cid(panel),
            protocol_params=artifact_cid(params),
            title=request.problem or "Untitled conclave case",
            opened_at=timestamp,
        )

        artifacts: list[dict] = [
            question, ledger, panel, params, *personas.values(), manifest_open
        ]
        identity_kp, identity_possession = make_key_publication_signed(
            seed=identity_seed, role="identity", published_at=timestamp
        )
        registry_kp, registry_possession = make_key_publication_signed(
            seed=registry_seed, role="persona-registry", published_at=timestamp
        )
        orchestrator_kp, certificate, certificate_sig = make_certificate_signed(
            orchestrator_seed=orchestrator_seed,
            identity_seed=identity_seed,
            case_manifest=artifact_cid(manifest_open),
            issued_at=timestamp,
        )
        orchestrator_possession = make_signature_signed(
            seed=orchestrator_seed, domain="orchestrator",
            payload=artifact_cid(orchestrator_kp), signed_at=timestamp,
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
                    seed=registry_seed, domain=DOMAIN_PERSONA_MANIFEST,
                    payload=artifact_cid(persona), signed_at=timestamp,
                )
            )
        for artifact in artifacts:
            self._ingest(artifact, timestamp)
        # persona roster documents stay resolvable offline (sourceDigest raws)
        for seat_id, persona in personas.items():
            digest = persona.get("sourceDigest")
            if digest is None:
                continue
            document = (request.agent_markdown or {}).get(seat_id)
            if document is not None:
                self._ingest_payload(f"{digest}.raw", Path(document).read_bytes(), timestamp)

        sth, sth_signature = make_signed_tree_head_signed(
            log_id=LOG_ID, tree_size=0, root_hash=tree_hash([]),
            seed=identity_seed, published_at=timestamp,
        )
        self._ingest(sth, timestamp)
        self._ingest(sth_signature, timestamp)

        self.state["meta"] = {
            "convened": convened,
            "advocates": advocates,
            "tokenBudget": request.token_budget,
            "title": request.problem or "Untitled conclave case",
        }
        self.state["orchestratorSeedB64"] = base64.b64encode(orchestrator_seed).decode("ascii")
        self.state["manifestCid"] = str(artifact_cid(manifest_open))
        self.state["sthCids"] = [str(artifact_cid(sth))]

        self.session_state = self.hub.open_session(case_ref, token_budget=request.token_budget)
        self.position = ["ready"]
        self._checkpoint()
        return case_ref

    def resume(self, case_ref: str) -> None:
        """Re-attach to a persisted case; continues at the recorded FSM row."""

        row = self.store.session(case_ref)
        if row is None:
            raise ValueError(f"no persisted case: {case_ref}")
        self.case_ref = case_ref
        self.state = _load_json(row["state"])
        self.position = _load_json(row["position"])
        budget = self.state["meta"].get("tokenBudget")
        self.session_state = self.hub.open_session(case_ref, token_budget=budget)
        state = self.session_state
        state.tokens_used = int(row["tokens_used"])
        for rung in self.state["degraded"]:
            state.degrade(rung)
        state.phase = _phase_for(self.position)

    # -- driving ----------------------------------------------------------------

    def drive(self) -> None:
        """Advance until a terminal position; one thread per session."""

        while True:
            with self._step_lock:
                if self.position[0] in ("closed", "aborted"):
                    return
                self._step()

    def _step(self) -> None:
        position = self.position
        head = position[0]
        if head == "ready":
            max_rounds = int(self._params_artifact().get("maxRounds", 4))
            if max_rounds <= 0:
                self.position = ["verdict"]
            else:
                self._enter_round(0)
        elif head == "round":
            round_index, stage = position[1], position[2]
            if stage == "turn":
                self._seat_step(round_index)
            elif stage == "distill":
                self._distill_step(round_index)
            elif stage == "consensus":
                self._consensus_step(round_index)
            elif stage == "close":
                self._close_round_step(round_index)
            else:
                raise RuntimeError(f"unknown round stage: {stage}")
        elif head == "verdict":
            self._verdict_step()
        else:
            raise RuntimeError(f"unknown FSM position: {position}")

    # -- round stages -------------------------------------------------------------

    def _apply_one_rung(self) -> None:
        """At a round boundary over budget, apply the next unused rung once.

        One rung per boundary keeps degradation observable step by step:
        ``batch`` labels subsequent routing, ``tighten-sparse-topology``
        reduces the next rounds' debating seats, and
        ``early-verdict-reduced-rounds`` (when the closing branch sees it)
        forces the verdict phase — it never precedes a round entry.
        """

        assert self.session_state is not None
        if self.session_state.token_budget is None:
            return
        if self.session_state.tokens_used < self.session_state.token_budget:
            return
        rung = next(
            (rung for rung in DEGRADATION_LADDER if rung not in self.session_state.degraded),
            None,
        )
        if rung is None:
            return  # ladder exhausted; the early-verdict rung already forces the stop
        self.session_state.degrade(rung)
        self.state["degraded"] = list(self.session_state.degraded)
        self.hub.publish(
            self.case_ref,
            "degraded",
            {"rung": rung, "tokensUsed": self.session_state.tokens_used,
             "tokenBudget": self.session_state.token_budget},
        )

    def _enter_round(self, round_index: int) -> None:
        self._apply_one_rung()
        assert self.session_state is not None
        if "early-verdict-reduced-rounds" in self.session_state.degraded:
            # the ladder's last rung stops the rounds: verdict from the record
            self.position = ["verdict"]
            self.session_state.phase = "verdict"
            return
        convened = self.state["meta"]["convened"]
        advocates = self.state["meta"]["advocates"]
        if "tighten-sparse-topology" in self.session_state.degraded:
            keep = (len(advocates) + 1) // 2
            participants = advocates[:keep] + [
                seat_id for seat_id in convened if seat_id not in advocates
            ]
        else:
            participants = list(convened)
        kind = "opening" if round_index == 0 else "challenge"
        record = self.state["rounds"].setdefault(str(round_index), _round_record())
        record["kind"] = kind
        record["participants"] = list(participants)
        self.session_state.phase = "round"
        self.session_state.round_index = round_index
        self.position = ["round", round_index, "turn", 0]
        self.hub.publish(
            self.case_ref,
            "round-started",
            {"roundIndex": round_index, "roundKind": kind, "participants": participants,
             "tokensUsed": self.session_state.tokens_used},
        )

    def _seat_step(self, round_index: int) -> None:
        record = self.state["rounds"][str(round_index)]
        participants = record["participants"]
        seat_index = self.position[3]
        if seat_index >= len(participants):
            self.position = ["round", round_index, "distill"]
            return
        seat_id = participants[seat_index]
        prompt_text, parts = self._seat_prompt(seat_id, round_index, record["kind"])
        call = self.client.call(seat_id, "round", round_index, record["kind"], prompt_text)
        turn_cid = self._commit_turn(seat_id, "round", round_index, prompt_text, parts, call)
        self._record_spend(call, len(prompt_text.encode("utf-8")), str(call.get("response", "")))
        record["allTurns"].append(turn_cid)
        record["speakingTurns"].append(turn_cid)
        self.state["seatFinal"][seat_id] = turn_cid
        assert self.session_state is not None
        self.hub.publish(
            self.case_ref,
            "turn-committed",
            {"seatId": seat_id, "roundIndex": round_index, "turnCid": turn_cid,
             "tokensUsed": self.session_state.tokens_used},
        )
        self.position = ["round", round_index, "turn", seat_index + 1]
        self._checkpoint()

    def _distill_step(self, round_index: int) -> None:
        record = self.state["rounds"][str(round_index)]
        params = self._params_artifact()
        prompt_text, parts = self._distill_prompt(params)
        call = self.client.call("orchestrator", "distill", round_index, record["kind"], prompt_text)
        record["distillModel"] = str(call.get("model_family", ""))
        record["distillCall"] = self._call_meta(call, parts)
        self._record_spend(call, len(prompt_text.encode("utf-8")), str(call.get("response", "")))
        parsed = parse_distillation(str(call.get("response", "")))
        record["distilled"] = parsed
        timestamp = self._timestamp()
        if parsed is None:
            record["distillError"] = (
                "mechanical distillation failed to produce a valid record; "
                "the round falls back to verbatim positions"
            )
        else:
            summary = make_summary(
                round_index=round_index,
                distilled_from=parse_cid_list(record["speakingTurns"]),
                positions=parsed["positions"],
                summary_text=parsed["summaryText"],
                open_disagreements=parsed.get("openDisagreements", []),
                written_at=timestamp,
                model_id=record["distillModel"] or None,
                word_count=len(parsed["summaryText"].split()) or None,
            )
            self._ingest(summary, timestamp)
            record["summaryCid"] = str(artifact_cid(summary))
        self.hub.publish(
            self.case_ref,
            "summary",
            {"roundIndex": round_index, "summaryCid": record["summaryCid"]},
        )
        self.position = ["round", round_index, "consensus"]
        self._checkpoint()

    def _consensus_step(self, round_index: int) -> None:
        record = self.state["rounds"][str(round_index)]
        prompt_text, parts = self._consensus_prompt()
        call = self.client.call("orchestrator", "consensus", round_index, record["kind"], prompt_text)
        record["consensusCall"] = self._call_meta(call, parts)
        self._record_spend(call, len(prompt_text.encode("utf-8")), str(call.get("response", "")))
        parsed = parse_consensus(str(call.get("response", "")))
        record["consensus"] = parsed
        if parsed is None:
            record["consensusError"] = "consensus scoring failed to produce a valid score"
        self.hub.publish(
            self.case_ref,
            "consensus-score",
            {"roundIndex": round_index, "score": parsed and parsed["consensusScore"],
             "activeDissent": parsed and parsed["activeDissent"]},
        )
        self.position = ["round", round_index, "close"]
        self._checkpoint()

    def _close_round_step(self, round_index: int) -> None:
        record = self.state["rounds"][str(round_index)]
        timestamp = self._timestamp()
        round_artifact = make_round(
            index=round_index,
            prev=parse(self.state["roundCids"][-1]) if self.state["roundCids"] else None,
            status="committed",
            participants=record["participants"],
            turns=parse_cid_list(record["allTurns"]) or None,
            distilled_summary=parse(record["summaryCid"]) if record["summaryCid"] else None,
            no_distillation_reason=(
                None
                if record["summaryCid"]
                else (record["distillError"] or "no distillation pass for this round")
            ),
            round_kind=record["kind"],
            opened_at=timestamp,
            closed_at=timestamp,
        )
        round_cid = artifact_cid(round_artifact)
        self._ingest(round_artifact, timestamp)
        self._ingest(
            make_signature_signed(
                seed=self._orchestrator_seed(), domain=DOMAIN_ROUND_ATTESTATION,
                payload=round_cid, signed_at=timestamp,
            ),
            timestamp,
        )
        self._commit_round_telemetry(round_index, round_cid)
        self.state["roundCids"].append(str(round_cid))

        assert self.session_state is not None
        note = (
            "degradation ladder applied: " + ", ".join(self.session_state.degraded)
            if self.session_state.degraded
            else None
        )
        fields = self._manifest_fields()
        manifest = make_manifest(
            case_id=self.case_ref,
            question=fields["question"],
            evidence_ledger=fields["evidenceLedger"],
            panel=fields["panel"],
            protocol_params=fields["protocolParams"],
            rounds=parse_cid_list(self.state["roundCids"]),
            supersedes=parse(self.state["manifestCid"]),
            title=self.state["meta"]["title"],
            opened_at=timestamp,
            note=note,
        )
        self.state["manifestCid"] = str(self._ingest(manifest, timestamp))

        params = self._params_artifact()
        early = consensus_reached(record["consensus"], int(params.get("earlyExitThresholdPct", 85)))
        if early or round_index + 1 >= int(params.get("maxRounds", 4)):
            self.position = ["verdict"]
            self.session_state.phase = "verdict"
        else:
            self._enter_round(round_index + 1)
        self._checkpoint()

    def _record_spend(self, call: dict, prompt_size: int, response_text: str) -> None:
        """Charge one provider call against the session budget (soft cap)."""

        assert self.session_state is not None
        tokens = self._token_block(call, prompt_size, len(response_text))
        total = int(tokens.get("inputTokens", 0)) + int(tokens.get("outputTokens", 0))
        self.session_state.spend(total)

    def _verdict_step(self) -> None:
        timestamp = self._timestamp()
        identity_seed = load_or_create_seed(self.keys_dir / IDENTITY_SEED_FILE)
        convened = self.state["meta"]["convened"]
        advocates = self.state["meta"]["advocates"]
        persona_cids = {seat_id: self._persona_cid(seat_id) for seat_id in convened}

        votes = []
        for seat_id in advocates:
            turn_cid = self.state["seatFinal"].get(seat_id)
            if turn_cid:
                votes.append(
                    {
                        "seatId": seat_id,
                        "persona": persona_cids[seat_id],
                        "stance": self._turn_text(turn_cid)[:160],
                        "weightMicro": 1_000_000,
                    }
                )

        if self.state["roundCids"]:
            final_key = max(self.state["rounds"], key=int)
            final_record = self.state["rounds"][final_key]
        else:
            # zero-round case: mirror the emitter's scaffold round so the DAG
            # keeps a final round for the verdict to chain to
            round_artifact = make_round(
                index=0,
                prev=None,
                status="committed",
                participants=convened,
                no_distillation_reason=(
                    "scaffold run: deterministic form validation only; no provider calls occurred"
                ),
                round_kind="scaffold",
                opened_at=timestamp,
                closed_at=timestamp,
            )
            round_cid = artifact_cid(round_artifact)
            self._ingest(round_artifact, timestamp)
            self._ingest(
                make_signature_signed(
                    seed=self._orchestrator_seed(), domain=DOMAIN_ROUND_ATTESTATION,
                    payload=round_cid, signed_at=timestamp,
                ),
                timestamp,
            )
            self.state["roundCids"].append(str(round_cid))
            final_record = _round_record()
            final_record["kind"] = "scaffold"
            self.state["rounds"]["0"] = final_record

        final_consensus = final_record.get("consensus") or {}
        active_dissent = final_consensus.get("activeDissent", [])
        dissent_seats = [seat_id for seat_id in active_dissent if seat_id in advocates]
        dissent_cids: list[str] = []
        dissent_links: list[Cid] = []
        artifacts: list[dict] = []
        for seat_id in dissent_seats:
            turn_cid = self.state["seatFinal"].get(seat_id)
            if turn_cid:
                grounds = self._turn_text(turn_cid)[:600]
                cited_ledger_ids = sorted(set(re.findall(r"E\d+", grounds)))
                cited_turns = [parse(turn_cid)]
            else:
                grounds = "dissent classified by the mechanical consensus scorer"
                cited_ledger_ids = []
                cited_turns = None
            dissent = make_dissent(
                round_cid=parse(self.state["roundCids"][-1]),
                seat_id=seat_id,
                persona=persona_cids[seat_id],
                grounds=grounds,
                cited_ledger_ids=cited_ledger_ids,
                cited_turns=cited_turns,
                filed_at=timestamp,
            )
            dissent_cid = artifact_cid(dissent)
            artifacts.append(dissent)
            artifacts.append(
                make_signature_signed(
                    seed=self._orchestrator_seed(), domain=DOMAIN_DISSENT_FILING,
                    payload=dissent_cid, signed_at=timestamp,
                )
            )
            dissent_cids.append(str(dissent_cid))
            dissent_links.append(dissent_cid)
        dissent_note = None
        if dissent_cids:
            dissent_note = (
                "active dissent auto-classified by the final consensus scorer; dissents "
                f"recorded as artifacts for seats: {', '.join(dissent_seats)}"
            )

        final_summary_cid = final_record.get("summaryCid")
        if final_summary_cid:
            advice = str(self.store.get(parse(final_summary_cid))["summaryText"]).strip()
            recommendation = "The Sovereign Conclave advises: " + advice
            verdict_note = (
                "mechanical verdict: standing protocol envelope applied to the "
                "distilled record"
            )
        else:
            recommendation = (
                "The Sovereign Conclave advises: the conclave validates form only; "
                "a seated deliberation with a distilled record is required before "
                "this question is decided."
            )
            verdict_note = "mechanical verdict: no distilled record; standing advice"

        verdict = make_verdict(
            manifest=parse(self.state["manifestCid"]),
            final_round=parse(self.state["roundCids"][-1]),
            decision=self.state["meta"]["title"],
            recommendation=recommendation,
            votes=votes,
            confidence="low",
            dissents=dissent_links or None,
            marshall_verification=_optional_cid(self.state["verificationTurnCid"]),
            dissent_recorded_note=dissent_note,
            issued_at=timestamp,
            note=verdict_note,
        )
        verdict_cid = artifact_cid(verdict)
        artifacts.append(verdict)
        artifacts.append(
            make_signature_signed(
                seed=identity_seed, domain=DOMAIN_VERDICT, payload=verdict_cid,
                signed_at=timestamp,
            )
        )
        fields = self._manifest_fields()
        manifest_final = make_manifest(
            case_id=self.case_ref,
            question=fields["question"],
            evidence_ledger=fields["evidenceLedger"],
            panel=fields["panel"],
            protocol_params=fields["protocolParams"],
            rounds=parse_cid_list(self.state["roundCids"]),
            verdict=verdict_cid,
            supersedes=parse(self.state["manifestCid"]),
            title=self.state["meta"]["title"],
            opened_at=timestamp,
        )
        artifacts.append(manifest_final)

        auto_t3 = None
        if dissent_cids:
            dissent_store = {
                artifact_cid(artifact): artifact
                for artifact in artifacts
                if artifact.get("type") == "Dissent"
            }
            share = weight_share_micro(verdict, dissent_store.get)
            if share is not None and share >= DEFAULT_WEIGHT_SHARE_MICRO:
                params = self._params_artifact()
                auto_t3 = make_appeal(
                    verdict=verdict_cid,
                    case_manifest=artifact_cid(manifest_final),
                    trigger="T3",
                    grounds=(
                        f"automatic: dissent weight share {share} micro >= "
                        f"{DEFAULT_WEIGHT_SHARE_MICRO} threshold at verdict issuance"
                    ),
                    filed_by="mechanical:T3",
                    filed_at=timestamp,
                    window_days=int(params.get("appealDefaultWindowDays", 30)),
                )
                artifacts.append(auto_t3)
                artifacts.append(
                    make_signature_signed(
                        seed=self._orchestrator_seed(), domain=DOMAIN_APPEAL_PETITION,
                        payload=artifact_cid(auto_t3), signed_at=timestamp,
                    )
                )

        # artifacts commit first; then the durable log growth; row records last
        for artifact in artifacts:
            self._ingest(artifact, timestamp)
        leaf_cids = [verdict_cid]
        if auto_t3 is not None:
            leaf_cids.append(artifact_cid(auto_t3))
        for leaf_cid in leaf_cids:
            tree_size, root = self.store.append_log_leaf(
                leaf_cid, timestamp, case_ref=self.case_ref
            )
            sth, sth_signature = make_signed_tree_head_signed(
                log_id=LOG_ID, tree_size=tree_size, root_hash=root,
                seed=identity_seed, published_at=timestamp,
            )
            self._ingest(sth, timestamp)
            self._ingest(sth_signature, timestamp)
            self.state["sthCids"].append(str(artifact_cid(sth)))

        self.state["manifestCid"] = str(artifact_cid(manifest_final))
        self.state["verdictCid"] = str(verdict_cid)
        self.state["dissentCids"] = dissent_cids
        if auto_t3 is not None:
            self.state["appealCid"] = str(artifact_cid(auto_t3))
        share_final = weight_share_micro(verdict, self.store.get)
        assert self.session_state is not None
        self.session_state.phase = "closed"
        self.hub.publish(
            self.case_ref,
            "verdict",
            {"verdictCid": str(verdict_cid), "dissentCids": dissent_cids,
             "manifestCid": self.state["manifestCid"], "shareMicro": share_final},
        )
        closed_payload: dict[str, Any] = {
            "verdictCid": str(verdict_cid),
            "manifestCid": self.state["manifestCid"],
        }
        if auto_t3 is not None:
            closed_payload["appealCid"] = str(artifact_cid(auto_t3))
        self.hub.publish(self.case_ref, "closed", closed_payload)
        self.position = ["closed"]
        self._checkpoint()

    # -- result surface -----------------------------------------------------------

    def result(self) -> dict[str, Any]:
        """API result surface once the run reaches a terminal position."""

        if not (self.position and self.position[0] in ("closed", "aborted")):
            raise ValueError("case is not terminal yet")
        return {
            "caseRef": self.case_ref,
            "verdictCid": self.state.get("verdictCid"),
            "manifestCid": self.state.get("manifestCid"),
            "appealCid": self.state.get("appealCid"),
            "dissentCids": list(self.state.get("dissentCids", [])),
            "tokensUsed": self.session_state.tokens_used if self.session_state else 0,
            "degraded": list(self.state.get("degraded", [])),
        }

    # -- private: persistence + resolution helpers ----------------------------

    def _ingest(self, artifact: dict, created_at: str) -> Cid:
        """Ingest one case artifact and track its CID in the session state."""

        cid = self.store.ingest(artifact, created_at)
        cid_str = str(cid)
        if cid_str not in self.state["artifacts"]:
            self.state["artifacts"].append(cid_str)
        return cid

    def _ingest_payload(self, name: str, payload: bytes, created_at: str) -> None:
        self.store.ingest_payload(name, payload, created_at)
        if not name.startswith("_") and name not in self.state["payloads"]:
            self.state["payloads"].append(name)

    def _checkpoint(self) -> None:
        """Persist the durable orchestration row; artifacts are already in."""

        assert self.session_state is not None
        self.store.upsert_session(
            self.case_ref,
            json.dumps(self.position),
            json.dumps(self.state, sort_keys=True),
            self.session_state.tokens_used,
            utc_now(),
        )

    def _timestamp(self) -> str:
        return str(self.state["timestamp"])

    def _payload_text(self, cid_str: str) -> str:
        return (self.store.payload(f"{cid_str}.raw") or b"").decode("utf-8", "replace")

    def _turn_text(self, turn_cid: str) -> str:
        """A turn's response text via its output-CID payload (not the turn CID)."""

        artifact = self.store.get(parse(turn_cid))
        assert isinstance(artifact, dict)
        return self._payload_text(str(artifact["output"]))

    def _manifest_fields(self) -> dict[str, Any]:
        manifest = self.store.get(parse(self.state["manifestCid"]))
        assert manifest is not None
        return manifest

    def _params_artifact(self) -> dict[str, Any]:
        params = self.store.get(self._manifest_fields()["protocolParams"])
        assert params is not None
        return params

    def _orchestrator_seed(self) -> bytes:
        return base64.b64decode(self.state["orchestratorSeedB64"])

    def _persona_cid(self, seat_id: str) -> Cid:
        """Resolve a seat's persona artifact CID from the store by seatId."""

        for cid in self.store.by_type("PersonaManifest"):
            persona = self.store.get(cid)
            if isinstance(persona, dict) and persona.get("seatId") == seat_id:
                return cid
        raise ValueError(f"persona artifact missing for seat: {seat_id}")

    def _commit_turn(
        self, seat_id: str, role: str, round_index: int,
        prompt_text: str, parts: dict[str, int], call: dict,
    ) -> str:
        """One provider call: Turn artifact + resolvable payloads + telemetry."""

        timestamp = self._timestamp()
        prompt = prompt_text.encode("utf-8")
        output = str(call.get("response", "")).encode("utf-8")
        prompt_cid, output_cid = raw_cid(prompt), raw_cid(output)
        turn = make_turn(
            round_index=round_index,
            seat_id=seat_id,
            persona=self._persona_cid(seat_id),
            input_context_hash=prompt_cid,
            model_id=str(call.get("model_family", "")),
            output=output_cid,
            citations=[],
            recorded_at=timestamp,
            provider_run=True,
            note=f"provider slot={call.get('slot')} provider={call.get('provider')} role={role}",
        )
        turn_cid = artifact_cid(turn)
        self._ingest(turn, timestamp)
        self._ingest_payload(f"{prompt_cid}.raw", prompt, timestamp)
        self._ingest_payload(f"{output_cid}.raw", output, timestamp)
        notes = []
        if call.get("ok") is False:
            notes.append("provider call failed; usage estimates are unreliable")
        telemetry = make_telemetry(
            subject=turn_cid,
            subject_kind="turn",
            tokens=self._token_block(call, len(prompt), len(output)),
            model_id=str(call.get("model_family", "")),
            provider=str(call.get("provider", "")),
            latency_ms=int(round(float(call.get("elapsed_s", 0.0)) * 1000)),
            estimated=call.get("usage") is None,
            batch=self.session_state is not None and "batch" in self.session_state.degraded,
            input_parts={
                "staticChars": parts["static"],
                "dynamicChars": parts["dynamic"],
                "suffixChars": parts["suffix"],
            },
            recorded_at=timestamp,
            note="; ".join(notes) or None,
        )
        self._ingest(telemetry, timestamp)
        return str(turn_cid)

    def _commit_round_telemetry(self, round_index: int, round_cid: Cid) -> None:
        """The round's deferred distill/consensus telemetries; subjects resolve."""

        record = self.state["rounds"][str(round_index)]
        timestamp = self._timestamp()
        targets = (
            {"callKey": "distillCall", "subjectKind": "summary", "summaryCid": record["summaryCid"]},
            {"callKey": "consensusCall", "subjectKind": "round", "summaryCid": None},
        )
        for target in targets:
            call_meta = record.get(target["callKey"])
            if call_meta is None:
                continue
            notes = []
            if target["callKey"] == "consensusCall":
                parsed = record["consensus"]
                if parsed is not None:
                    dissent_text = ", ".join(parsed["activeDissent"]) or "none"
                    notes.append(
                        f"consensusScore={parsed['consensusScore']}; activeDissent={dissent_text}"
                    )
                else:
                    notes.append(record["consensusError"] or "consensus unparseable")
            if not call_meta["ok"]:
                notes.append("provider call failed; usage estimates are unreliable")
            subject = parse(target["summaryCid"]) if target["summaryCid"] else round_cid
            self._ingest(
                make_telemetry(
                    subject=subject,
                    subject_kind=target["subjectKind"],
                    tokens=self._token_block(call_meta, call_meta["static"], call_meta["dynamic"]),
                    model_id=call_meta["model_family"],
                    provider=call_meta["provider"],
                    latency_ms=call_meta["latency_ms"],
                    estimated=call_meta["estimated"],
                    batch=call_meta["batch"],
                    input_parts=call_meta["input_parts"],
                    recorded_at=timestamp,
                    note="; ".join(notes) or None,
                ),
                timestamp,
            )

    # -- prompts ------------------------------------------------------------------

    def _seat_prompt(self, seat_id: str, round_index: int, round_kind: str) -> tuple[str, dict[str, int]]:
        """Compose a seat round prompt with sized static/dynamic/suffix parts."""

        static = _STANDING_PROTOCOL_TEXT
        dynamic = (
            f"Question: {self.state['meta']['title']}\n"
            f"Evidence ledger (frozen before Round 1): {', '.join(self._ledger_ids()) or 'none'}\n"
            f"Round {round_index} ({round_kind}): give your position for the record."
        )
        suffix = (
            f"You are seat {seat_id} of the conclave panel. "
            "Argue the lens your roster persona records."
        )
        return static + "\n" + dynamic + "\n\n" + suffix, {
            "static": len(static), "dynamic": len(dynamic), "suffix": len(suffix),
        }

    def _distill_prompt(self, params: dict) -> tuple[str, dict[str, int]]:
        static = _STANDING_PROTOCOL_TEXT
        dynamic = (
            f"Question: {self.state['meta']['title']}\n"
            "Distill this round for the record. Reply with exactly one JSON object:\n"
            '{"summaryText": str, "positions": [{"seatId": str, "stance": str, '
            '"citations": [str]}], "openDisagreements": [str]}\n'
            f"Stay within the {int(params.get('summaryTokenBudget', 1200))} token budget."
        )
        return static + "\n" + dynamic, {
            "static": len(static), "dynamic": len(dynamic), "suffix": 0,
        }

    def _consensus_prompt(self) -> tuple[str, dict[str, int]]:
        static = _STANDING_PROTOCOL_TEXT
        dynamic = (
            f"Question: {self.state['meta']['title']}\n"
            "Score the recorded round. Reply with exactly one JSON object:\n"
            '{"consensusScore": int (0-100), "activeDissent": [seatIds]}\n'
            "A seat counts as active dissent ONLY if it still rejects the emerging "
            "direction on recorded grounds."
        )
        return static + "\n" + dynamic, {
            "static": len(static), "dynamic": len(dynamic), "suffix": 0,
        }

    def _ledger_ids(self) -> list[str]:
        ledger = self.store.get(self._manifest_fields()["evidenceLedger"])
        assert ledger is not None
        return [str(entry.get("id")) for entry in ledger.get("entries", [])]

    # -- static record helpers --------------------------------------------------

    def _call_meta(self, call: dict, parts: dict[str, int]) -> dict[str, Any]:
        """Telemetry metadata snapshot for a mechanical call (round-deferred)."""

        usage = call.get("usage")
        return {
            "model_family": str(call.get("model_family", "")),
            "provider": str(call.get("provider", "")),
            "ok": call.get("ok") is not False,
            "static": parts["static"],
            "dynamic": parts["dynamic"],
            "latency_ms": int(round(float(call.get("elapsed_s", 0.0)) * 1000)),
            "usage": usage,
            "estimated": usage is None,
            "batch": self.session_state is not None and "batch" in self.session_state.degraded,
            "input_parts": {
                "staticChars": int(parts["static"]),
                "dynamicChars": int(parts["dynamic"]),
                "suffixChars": int(parts["suffix"]),
            },
        }

    @staticmethod
    def _token_block(call: dict, prompt_size: int, output_size: int) -> dict[str, int]:
        usage = call.get("usage")
        if usage is None:
            return {
                "inputTokens": prompt_size // 4,
                "outputTokens": output_size // 4,
            }
        return {
            "inputTokens": int(usage.get("inputTokens", 0) or 0),
            "outputTokens": int(usage.get("outputTokens", 0) or 0),
            "cacheReadTokens": int(usage.get("cacheReadTokens", 0) or 0),
            "cacheWriteTokens": int(usage.get("cacheWriteTokens", 0) or 0),
        }


def _optional_cid(cid_str: str | None) -> Cid | None:
    return parse(cid_str) if cid_str else None
