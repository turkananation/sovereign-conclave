"""M6 HTTP layer: a stdlib host for the conclave server (roadmap M6 item 2).

Endpoint verbs follow the roadmap contract (Serverpod-shaped signatures,
stdlib implementation):

- ``POST /convene``  — open a case (Question + EvidenceLedgerDraft +
  ProtocolParams); session-token authenticated response mints the token.
- ``GET  /watch``    — SSE stream of DeliberationEvents for one case
  (civic-public; ``?caseRef=...&after=<ordinal>[&timeout=<s>]``).
- ``GET  /verdict``  — verdict summary once terminal (civic public).
- ``POST /petition`` — file an appeal through the M5 engine bridge
  (session token).
- ``POST /screening`` — record a T1 Marshall screening (session token).
- ``GET  /artifact/<cid>`` — public artifact bytes (CBOR) or ``.raw``
  payload.
- ``GET  /prove/<cid>[?caseRef=...]`` — public RFC 6962 inclusion proof.
- ``GET  /latestSTH[?caseRef=...]`` — public latest signed tree head.

Writes are session-token authenticated (``X-Conclave-Token``); reads are
civic-public, per the roadmap's access split. Each convene runs its FSM on
a daemon thread; the store and hub carry concurrency, so the HTTP layer
only parses, routes, and serializes.
"""

from __future__ import annotations

import base64
import json
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from conclave_core.appeals import AppealError
from conclave_core.artifacts import make_protocol_params
from conclave_core.cid import parse

from .appeals import AppealBridge
from .materialize import materialize_case
from .orchestrator import CaseRun, ConveneRequest, SeatClient
from .sessions import SessionHub
from .store import ArtifactStore

_CID_PATTERN = re.compile(r"^/artifact/([a-z0-9]+)$")
_PROVE_PATTERN = re.compile(r"^/prove/([a-z0-9]+)$")

_PROTOCOL_PARAM_FIELDS = {
    # HTTP contract (camelCase) -> make_protocol_params kwargs (snake_case)
    "quorum": "quorum",
    "maxRounds": "max_rounds",
    "wordBudgetRound1": "word_budget_round1",
    "wordBudgetRound2": "word_budget_round2",
    "wordBudgetCrossExamination": "word_budget_cross_examination",
    "summaryTokenBudget": "summary_token_budget",
    "earlyExitThresholdPct": "early_exit_threshold_pct",
    "appealDefaultWindowDays": "appeal_default_window_days",
}


class RequestError(Exception):
    """A request the HTTP layer refuses (status + message)."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class ServerApp:
    """Wiring for one conclave server process: store + hub + bridge."""

    def __init__(
        self,
        keys_dir: Path,
        db_path: Path,
        roster_path: Path | None = None,
    ) -> None:
        self.keys_dir = Path(keys_dir)
        self.store = ArtifactStore(db_path)
        self.hub = SessionHub()
        self.bridge = AppealBridge(self.store, self.keys_dir)
        self.roster_path = Path(roster_path) if roster_path else Path("configs/conclave-roster.json")
        self._tokens: dict[str, str] = {}
        self._runs: dict[str, CaseRun] = {}
        self._write_lock = threading.Lock()

    # -- session token auth ---------------------------------------------------

    def _require_token(self, case_ref: str, provided: str | None) -> None:
        expected = self._tokens.get(case_ref)
        if expected is None:
            raise RequestError(404, f"no active session for case: {case_ref}")
        if not provided or not secrets.compare_digest(provided, expected):
            raise RequestError(401, "missing or invalid X-Conclave-Token header")

    # -- operations ------------------------------------------------------------

    def roster(self) -> dict[str, Any]:
        config = json.loads(self.roster_path.read_text(encoding="utf-8"))
        return config

    def _resolve_seats(self, body: dict[str, Any], config: dict[str, Any]) -> list[str]:
        if body.get("seats"):
            seats = body["seats"]
            if not isinstance(seats, list) or not all(isinstance(s, str) for s in seats):
                raise RequestError(400, "seats must be a list of seat ids")
            return list(seats)
        profile_id = body.get("profile") or config.get("default_profile")
        profiles = {profile["id"]: profile for profile in config.get("profiles", [])}
        profile = profiles.get(profile_id)
        if profile is None:
            raise RequestError(400, f"unknown profile: {profile_id!r}")
        return list(profile["seats"])

    def convene(self, body: dict[str, Any]) -> dict[str, Any]:
        """Open a case; mint the session token; start the FSM thread."""

        if not isinstance(body, dict):
            raise RequestError(400, "the convene body must be a JSON object")
        problem = str(body.get("problem", "") or "").strip()
        if not problem:
            raise RequestError(400, "problem (the Question text) is required")

        config = self.roster()
        seats = self._resolve_seats(body, config)
        marshall = str(body.get("marshallId") or config["marshall"])

        ledger_draft = body.get("ledgerDraft", [])
        if not isinstance(ledger_draft, list):
            raise RequestError(400, "ledgerDraft must be a list of draft entries")

        param_kwargs: dict[str, Any] = {}
        raw_params = body.get("protocolParams")
        if raw_params is not None:
            if not isinstance(raw_params, dict):
                raise RequestError(400, "protocolParams must be a JSON object")
            unknown = sorted(set(raw_params) - set(_PROTOCOL_PARAM_FIELDS))
            if unknown:
                raise RequestError(400, f"unknown protocolParams fields: {', '.join(unknown)}")
            param_kwargs = {
                _PROTOCOL_PARAM_FIELDS[key]: raw_params[key]
                for key in _PROTOCOL_PARAM_FIELDS
                if key in raw_params
            }
        params = make_protocol_params(recorded_by="session-orchestrator", **param_kwargs)

        token_budget = body.get("tokenBudget")
        if token_budget is not None and (not isinstance(token_budget, int) or isinstance(token_budget, bool)):
            raise RequestError(400, "tokenBudget must be an integer")

        agent_markdown: dict[str, Path] = {}
        raw_agents = body.get("agentMarkdown") or {}
        if not isinstance(raw_agents, dict):
            raise RequestError(400, "agentMarkdown must map seat ids to markdown text")
        roster_seats = {seat["id"]: seat for seat in config["seats"]}
        for seat_id, text in raw_agents.items():
            seat = roster_seats.get(seat_id)
            if seat is None:
                raise RequestError(400, f"agentMarkdown for unknown seat: {seat_id!r}")
            document = Path(self.keys_dir) / "agent-docs" / f"{seat_id}.md"
            document.parent.mkdir(parents=True, exist_ok=True)
            document.write_text(str(text), encoding="utf-8")
            agent_markdown[seat_id] = document

        request = ConveneRequest(
            profile_id=str(body.get("profileId") or body.get("profile") or "petitioner"),
            problem=problem,
            roster={"version": config["version"], "seats": config["seats"]},
            seats=seats,
            marshall_id=marshall,
            ledger_entries=ledger_draft,
            token_budget=token_budget,
            protocol_params=params,
            agent_markdown=agent_markdown or None,
            timestamp=body.get("timestamp"),
        )

        run = CaseRun(self.store, self.hub, self.keys_dir, SeatlessClient())
        case_ref = run.convene(request)
        token = secrets.token_urlsafe(24)
        with self._write_lock:
            self._tokens[case_ref] = token
            self._runs[case_ref] = run
        thread = threading.Thread(target=self._drive_run, args=(run,), daemon=True)
        thread.start()
        return {
            "caseRef": case_ref,
            "token": token,
            "seats": seats,
            "marshallId": marshall,
        }

    def _drive_run(self, run: CaseRun) -> None:
        try:
            run.drive()
        except Exception as error:  # surface, never thread-crash silently
            self.hub.publish(run.case_ref, "aborted", {"reason": str(error)})
            raise

    def watch_stream(
        self, case_ref: str, after: int, emit: Callable[[dict], None], timeout: float | None
    ) -> None:
        """SSE body: emit each DeliberationEvent after ``after`` until closed.

        Callers validate the case exists before streaming starts; the
        terminal event (closed / aborted) prices the watcher's stream off.
        """

        deadline = time.monotonic() + timeout if timeout else None
        while True:
            events = self.hub.events(case_ref, after)
            if not events:
                event = self.hub.wait_for(case_ref, after, timeout=15.0)
                if event is not None:
                    events = [event]
                elif deadline and time.monotonic() >= deadline:
                    return
            for event in events:
                emit(event)
                after = int(event["ordinal"])
                if event["kind"] in ("closed", "aborted"):
                    return
            if deadline and time.monotonic() >= deadline:
                return

    def knows_case(self, case_ref: str) -> bool:
        return case_ref in self._tokens or self.store.session(case_ref) is not None

    def verdict(self, case_ref: str) -> dict[str, Any]:
        row = self.store.session(case_ref)
        if row is None:
            raise RequestError(404, f"unknown case: {case_ref}")
        state = json.loads(row["state"])
        position = json.loads(row["position"])
        if not state.get("verdictCid"):
            raise RequestError(409, f"case has no verdict yet (phase {_phase_of(position)})")
        return {
            "caseRef": case_ref,
            "verdictCid": state["verdictCid"],
            "manifestCid": state.get("manifestCid"),
            "appealCid": state.get("appealCid"),
            "dissentCids": state.get("dissentCids", []),
            "degraded": state.get("degraded", []),
            "tokensUsed": int(row["tokens_used"]),
        }

    def petition(self, body: dict[str, Any], token: str | None) -> dict[str, Any]:
        case_ref = self._case_ref(body, "petition")
        self._require_token(case_ref, token)
        trigger = str(body.get("trigger", "") or "").strip().upper()
        if trigger not in ("T1", "T2", "T3"):
            raise RequestError(400, "trigger must be T1, T2, or T3 (T4 defers to v0.3)")
        grounds = str(body.get("grounds", "") or "").strip()
        if not grounds:
            raise RequestError(400, "grounds are required")
        documents = body.get("documents") or []
        try:
            return self.bridge.file_petition(
                case_ref,
                trigger=trigger,
                grounds=grounds,
                filed_by=str(body.get("filedBy") or "petitioner"),
                documents=documents,
            )
        except AppealError as error:
            raise RequestError(422, str(error))

    def screening(self, body: dict[str, Any], token: str | None) -> dict[str, Any]:
        case_ref = self._case_ref(body, "screening")
        self._require_token(case_ref, token)
        appeal_cid = str(body.get("appealRef", "") or "").strip()
        if not appeal_cid:
            raise RequestError(400, "appealRef is required")
        decision = str(body.get("decision", "") or "").strip()
        if decision not in ("admitted", "rejected"):
            raise RequestError(400, "decision must be 'admitted' or 'rejected'")
        reasons = str(body.get("reasons", "") or "").strip()
        if not reasons:
            raise RequestError(400, "reasons are required")
        try:
            return self.bridge.screen_petition(
                case_ref,
                appeal_cid=appeal_cid,
                decision=decision,
                screened_by=str(body.get("screenedBy") or "marshall"),
                reasons=reasons,
            )
        except AppealError as error:
            raise RequestError(422, str(error))

    def artifact_bytes(self, cid_str: str) -> tuple[bytes, str]:
        """Public artifact media: CBOR for artifacts, raw for payloads."""

        try:
            parse(cid_str)
        except ValueError as error:
            raise RequestError(400, f"invalid CID: {error}")
        raw = self.store.raw(cid_str)
        if raw is not None:
            return raw, "application/cbor"
        payload = self.store.payload(f"{cid_str}.raw")
        if payload is not None:
            return payload, "text/plain; charset=utf-8"
        raise RequestError(404, f"unknown artifact: {cid_str}")

    def prove(self, cid_str: str, case_ref: str | None) -> dict[str, Any]:
        try:
            parse(cid_str)
        except ValueError as error:
            raise RequestError(400, f"invalid CID: {error}")
        case_refs = self.store.leaf_case_refs(cid_str)
        if not case_refs:
            raise RequestError(404, f"cid is not a logged leaf: {cid_str}")
        if case_ref is None:
            if len(case_refs) > 1:
                raise RequestError(
                    409, f"cid is logged in several cases; pass caseRef: {', '.join(case_refs)}"
                )
            case_ref = case_refs[0]
        elif case_ref not in case_refs:
            raise RequestError(404, f"cid {cid_str} is not a leaf of case {case_ref}")
        leaves = self.store.leaves(case_ref)
        index = next(i for i, leaf in enumerate(leaves) if str(leaf) == cid_str)
        tree_size = len(leaves)
        return {
            "leafCid": cid_str,
            "caseRef": case_ref,
            "index": index,
            "treeSize": tree_size,
            "path": [base64.b64encode(node).decode("ascii")
                     for node in self.store.inclusion_proof(case_ref, index, tree_size)],
        }

    def latest_sth(self, case_ref: str | None) -> dict[str, Any]:
        if case_ref is not None:
            head = self.store.latest_head(case_ref)
            if head is None:
                raise RequestError(404, f"no transparency log entries for case: {case_ref}")
            return self._sth_payload(case_ref, head)
        rows = [(ref, self.store.latest_head(ref)) for ref in self.store.session_refs()]
        heads = [(ref, head) for ref, head in rows if head is not None]
        if not heads:
            raise RequestError(404, "no transparency log entries hosted yet")
        best_ref, best_head = max(heads, key=lambda item: (item[1][2], item[1][0]))
        return self._sth_payload(best_ref, best_head)

    def _sth_payload(self, case_ref: str, head: tuple[int, bytes, str]) -> dict[str, Any]:
        row = self.store.session(case_ref)
        state = json.loads(row["state"]) if row else {}
        sth_cids = state.get("sthCids", [])
        return {
            "caseRef": case_ref,
            "treeSize": head[0],
            "rootHash": base64.b64encode(head[1]).decode("ascii"),
            "publishedAt": head[2],
            "sthCid": sth_cids[-1] if sth_cids else None,
        }

    def materialize(self, case_ref: str, out_dir: Path) -> Path:
        """Operational helper: write the case's verifier bundle."""

        return materialize_case(self.store, self.keys_dir, case_ref, out_dir)

    # -- helpers -------------------------------------------------------------

    def _case_ref(self, body: dict[str, Any], label: str) -> str:
        if not isinstance(body, dict):
            raise RequestError(400, f"the {label} body must be a JSON object")
        case_ref = str(body.get("caseRef", "") or "").strip()
        if not case_ref:
            raise RequestError(400, "caseRef is required")
        return case_ref

    def close(self) -> None:
        self.store.close()


class SeatlessClient(SeatClient):
    """Default adapter: every seat runs the local deterministic voice.

    The wired server accepts a provider adapter through
    ``CONCLAVE_PROVIDER_CMD`` (M7); without one, seats answer with the
    standing protocol voice and the distiller summarizes the seats that
    actually spoke (the client observes them from the round calls).
    """

    def __init__(self) -> None:
        self._speakers: dict[int, list[str]] = {}

    def call(self, seat_id: str, role: str, round_index: int, round_kind: str, prompt: str) -> dict:
        if role == "round":
            self._speakers.setdefault(round_index, []).append(seat_id)
            return {
                "response": (
                    f"Standing position from {seat_id} for round {round_index} ({round_kind}). "
                    "The recorded question finds its answer in the ledger's own terms; "
                    "the conclave advises care before an irreversible step. confidence: low"
                ),
                "model_family": "conclave-standing",
                "provider": "conclave-server",
                "slot": "local",
                "usage": None,
                "elapsed_s": 0.0,
            }
        if role == "distill":
            speakers = self._speakers.get(round_index, [])
            return {
                "response": json.dumps(
                    {
                        "summaryText": (
                            f"Round {round_index} recorded standing positions from "
                            f"{', '.join(speakers) or 'the panel'}."
                        ),
                        "positions": [
                            {
                                "seatId": seat_id,
                                "stance": (
                                    "proceed with care; the ledger supports an "
                                    "advisory-only recommendation"
                                ),
                                "citations": [],
                            }
                            for seat_id in speakers
                        ],
                        "openDisagreements": [],
                    }
                ),
                "model_family": "conclave-standing",
                "provider": "conclave-server",
                "usage": None,
                "elapsed_s": 0.0,
            }
        if role == "consensus":
            return {
                "response": json.dumps({"consensusScore": 90, "activeDissent": []}),
                "model_family": "conclave-standing",
                "provider": "conclave-server",
                "usage": None,
                "elapsed_s": 0.0,
            }
        raise ValueError(f"unknown seat role: {role}")


class _ConclaveHandler(BaseHTTPRequestHandler):
    """Route table for the conclave server's HTTP verbs."""

    server_version = "conclave-server/0.2"
    protocol_version = "HTTP/1.1"

    app: ServerApp  # set via server.app (deferred attribute)

    # -- plumbing ------------------------------------------------------------

    @property
    def server_app(self) -> ServerApp:
        return self.server.app  # type: ignore[attr-defined]

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RequestError(400, f"invalid JSON body: {error}")
        return body

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, error: Exception) -> None:
        status = getattr(error, "status", 500)
        message = getattr(error, "message", str(error))
        self._send_json(status, {"error": message})

    def _send_bytes(self, status: int, body: bytes, media_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet under tests
        pass

    # -- verbs ----------------------------------------------------------------

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        try:
            if parsed.path == "/watch":
                self._watch(params)
            elif parsed.path == "/verdict":
                case_ref = params.get("caseRef", "")
                if not case_ref:
                    raise RequestError(400, "caseRef is required")
                self._send_json(200, self.server_app.verdict(case_ref))
            elif parsed.path == "/latestSTH":
                self._send_json(200, self.server_app.latest_sth(params.get("caseRef")))
            else:
                match = _CID_PATTERN.match(parsed.path)
                if match:
                    data, media_type = self.server_app.artifact_bytes(match.group(1))
                    self._send_bytes(200, data, media_type)
                    return
                match = _PROVE_PATTERN.match(parsed.path)
                if match:
                    self._send_json(200, self.server_app.prove(match.group(1), params.get("caseRef")))
                    return
                raise RequestError(404, f"no such endpoint: {parsed.path}")
        except RequestError as error:
            self._send_error_json(error)
        except Exception as error:  # pragma: no cover - unexpected
            self._send_error_json(RequestError(500, str(error)))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        token = self.headers.get("X-Conclave-Token")
        try:
            if parsed.path == "/convene":
                self._send_json(201, self.server_app.convene(self._read_body()))
            elif parsed.path == "/petition":
                self._send_json(201, self.server_app.petition(self._read_body(), token))
            elif parsed.path == "/screening":
                self._send_json(201, self.server_app.screening(self._read_body(), token))
            else:
                raise RequestError(404, f"no such endpoint: {parsed.path}")
        except RequestError as error:
            self._send_error_json(error)
        except AppealError as error:
            self._send_json(422, {"error": str(error)})
        except Exception as error:  # pragma: no cover - unexpected
            self._send_error_json(RequestError(500, str(error)))

    # -- SSE ------------------------------------------------------------------

    def _watch(self, params: dict[str, str]) -> None:
        case_ref = params.get("caseRef", "")
        if not case_ref:
            raise RequestError(400, "caseRef is required")
        after = int(params.get("after", 0) or 0)
        timeout_param = params.get("timeout")
        timeout = float(timeout_param) if timeout_param is not None else None

        app = self.server_app
        # case-existence errors must be sent BEFORE the stream headers so the
        # client sees a proper 404 rather than an empty event stream
        if not app.knows_case(case_ref):
            raise RequestError(404, f"unknown case: {case_ref}")

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(event: dict) -> None:
            data = json.dumps(event, sort_keys=True).encode("utf-8")
            self.wfile.write(b"id: " + str(event["ordinal"]).encode("ascii") + b"\n")
            self.wfile.write(b"data: " + data + b"\n\n")
            self.wfile.flush()

        try:
            app.watch_stream(case_ref, after, emit, timeout)
        except (BrokenPipeError, ConnectionResetError):
            pass  # watcher disconnected mid-stream; the case keeps running


class ThreadingConclaveServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_server(
    app: ServerApp, host: str = "127.0.0.1", port: int = 0
) -> ThreadingConclaveServer:
    """Bind the handler to the app; port 0 picks an ephemeral port (tests)."""

    server = ThreadingConclaveServer((host, port), _ConclaveHandler)
    server.app = app
    return server


def _phase_of(position: list) -> str:
    if not position:
        return "unknown"
    head = position[0]
    if head == "round":
        return f"round:{position[1]}:{position[2]}"
    return str(head)
