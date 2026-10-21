"""Live session state for the conclave server (roadmap M6 item 3).

Deployment note (documented deviation): production targets Memorystore
(Redis) for live session state and pub/sub fan-out; the stdlib build keeps
both in-process under locks. The contract is identical: per-session FSM
position, per-session token budget counters, and progress-event fan-out to
watchers.

Events carry a per-case monotonically increasing ordinal. A watcher attaches
at the ordinal it has already seen and pulls events with ``wait_for``; the
terminal event (verdict / closed / aborted) prices the watcher's stream off.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

EVENT_KINDS = (
    "convened",
    "round-started",
    "turn-committed",
    "summary",
    "consensus-score",
    "verdict",
    "degraded",
    "closed",
    "aborted",
)

# graceful degradation ladder (roadmap item 5; applied in this order)
DEGRADATION_LADDER = ("batch", "tighten-sparse-topology", "early-verdict-reduced-rounds")


@dataclass
class SessionState:
    """Live state for one deliberation: FSM position plus budget counters."""

    case_ref: str
    phase: str = "convened"  # convened | round | distill | consensus | verdict | closed | aborted
    round_index: int | None = None
    tokens_used: int = 0
    token_budget: int | None = None
    degraded: list[str] = field(default_factory=list)
    note: str | None = None  # terminal/close note (never silent degradation)

    def remaining_tokens(self) -> int | None:
        if self.token_budget is None:
            return None
        return max(0, self.token_budget - self.tokens_used)

    def spend(self, tokens: int) -> int:
        """Record consumed tokens; returns the seat's projected remaining budget."""

        if tokens < 0:
            raise ValueError("token spend must be non-negative")
        self.tokens_used += tokens
        if self.token_budget is None:
            return 0
        return max(0, self.token_budget - self.tokens_used)

    def degrade(self, rung: str) -> None:
        """Record one applied degradation rung once (idempotent, ordered)."""

        if rung not in DEGRADATION_LADDER:
            raise ValueError(f"unknown degradation rung: {rung}")
        if rung not in self.degraded:
            self.degraded.append(rung)

    def terminal(self) -> bool:
        return self.phase in ("closed", "aborted")


class SessionHub:
    """Authoritative live sessions and event fan-out (in-process Memorystore)."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._sessions: dict[str, SessionState] = {}
        self._events: dict[str, list[dict]] = {}

    # -- sessions ------------------------------------------------------------

    def open_session(self, case_ref: str, token_budget: int | None = None) -> SessionState:
        """Create (or re-open) a session for ``case_ref`` in one atomic step."""

        with self._condition:
            existed = case_ref in self._sessions
            if existed:
                state = self._sessions[case_ref]
                if token_budget is not None:
                    state.token_budget = token_budget
                return state
            state = SessionState(case_ref=case_ref, token_budget=token_budget)
            self._sessions[case_ref] = state
            self._events[case_ref] = []
            self._publish_locked(
                state,
                "convened",
                {"tokenBudget": token_budget},
            )
            self._condition.notify_all()
            return state

    def state(self, case_ref: str) -> SessionState | None:
        with self._condition:
            return self._sessions.get(case_ref)

    def states(self) -> list[SessionState]:
        with self._condition:
            return list(self._sessions.values())

    # -- events ---------------------------------------------------------------

    def _publish_locked(self, state: SessionState, kind: str, payload: dict) -> dict:
        ordinal = len(self._events[state.case_ref]) + 1
        event = {
            "ordinal": ordinal,
            "caseRef": state.case_ref,
            "kind": kind,
            "phase": state.phase,
            "roundIndex": state.round_index,
            "at": time.time(),
            "payload": payload,
        }
        self._events[state.case_ref].append(event)
        return event

    def publish(self, case_ref: str, kind: str, payload: dict | None = None) -> dict:
        """Append one progress event and wake every waiting watcher."""

        if kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind: {kind}")
        with self._condition:
            state = self._sessions.get(case_ref)
            if state is None:
                raise ValueError(f"no session open for case: {case_ref}")
            event = self._publish_locked(state, kind, dict(payload or {}))
            self._condition.notify_all()
        return event

    def events(self, case_ref: str, after_ordinal: int = 0) -> list[dict]:
        """Snapshot of everything after ``after_ordinal`` (non-blocking)."""

        with self._condition:
            history = self._events.get(case_ref)
            return list(history[after_ordinal:]) if history else []

    def wait_for(self, case_ref: str, after_ordinal: int, timeout: float = 30.0) -> dict | None:
        """Block until an event past ``after_ordinal`` exists; None on timeout."""

        deadline = time.monotonic() + timeout
        with self._condition:
            history = self._events.get(case_ref)
            while history is None or len(history) <= after_ordinal:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                if not self._condition.wait_for(lambda: len(self._events.get(case_ref, ())) > after_ordinal, remaining):
                    return None
                history = self._events.get(case_ref)
            return history[after_ordinal]

    # -- budget ---------------------------------------------------------------

    def spend(self, case_ref: str, tokens: int) -> int:
        """Record tokens against the session budget; returns remaining tokens."""

        with self._condition:
            state = self._sessions.get(case_ref)
            if state is None:
                raise ValueError(f"no session open for case: {case_ref}")
            remaining = state.spend(tokens)
            self._condition.notify_all()
        return remaining
