#!/usr/bin/env python3
"""Opt-in provider-backed deliberation for the Sovereign Conclave runner.

This module is OFF by default. It only runs when the user passes
``--provider-run`` to ``bin/conclave`` *and* a provider is reachable through the
environment. It never reads credentials from files and never commits them
(Directive D-5: local-first, zero-key default; optional routing via env only).
It also never authorizes an action (Directive D-4: advise, never act).

Two zero-dependency client mechanisms are supported, chosen from the environment:

1. ``CONCLAVE_PROVIDER_CMD`` -- a command template that receives the prompt on
   stdin and prints the completion on stdout. The universal, provider-agnostic
   escape hatch. ``{provider}``, ``{model_family}``, ``{slot}`` and ``{seat}``
   are substituted. This is what the test-suite uses with a local stub.
2. ``ANTHROPIC_API_KEY`` -- a built-in Anthropic Messages adapter over urllib,
   for single-provider convenience. Model comes from ``CONCLAVE_ANTHROPIC_MODEL``
   (default ``claude-sonnet-4-6``).

If neither is present, ``get_client`` returns ``None`` and the runner falls back
to the deterministic scaffold.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol


# --------------------------------------------------------------------------- #
# Provider config parsing (dependency-free; matches the documented YAML shape).
# --------------------------------------------------------------------------- #

@dataclass
class ProviderConfig:
    slots: dict[str, dict[str, str]] = field(default_factory=dict)
    seat_slots: dict[str, str] = field(default_factory=dict)
    fallback_slot: str | None = None
    key_source: str | None = None
    mechanical_slot: str | None = None   # cascade tier for tally/distill/consensus (haiku-class or local)
    pricing: dict[str, dict[str, int]] = field(default_factory=dict)

    def slot_for_kind(self, kind: str) -> str:
        """Model-cascade routing: every mechanical call lands on the cheap tier."""

        if kind in ("distill", "consensus", "tally"):
            return self.mechanical_slot or self.fallback_slot or "balanced"
        return self.fallback_slot or "balanced"


def parse_provider_config(text: str) -> ProviderConfig:
    cfg = ProviderConfig()
    section: str | None = None
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z]", line):
            section = line.split(":", 1)[0].strip()
            current_key = None
            continue
        if section == "defaults":
            match = re.match(r"^\s+(\w+):\s*(\S+)\s*$", line)
            if match:
                if match.group(1) == "fallback_slot":
                    cfg.fallback_slot = match.group(2)
                elif match.group(1) == "key_source":
                    cfg.key_source = match.group(2)
                elif match.group(1) == "mechanical_slot":
                    cfg.mechanical_slot = match.group(2)
        elif section == "slots":
            slot_header = re.match(r"^  ([A-Za-z][\w-]*):\s*$", line)
            if slot_header:
                current_key = slot_header.group(1)
                cfg.slots[current_key] = {}
                continue
            attr = re.match(r"^    (\w+):\s*(\S+)\s*$", line)
            if attr and current_key:
                cfg.slots[current_key][attr.group(1)] = attr.group(2)
        elif section == "seat_slots":
            seat = re.match(r"^  (conclave-[a-z0-9-]+):\s*([A-Za-z][\w-]*)\s*$", line)
            if seat:
                cfg.seat_slots[seat.group(1)] = seat.group(2)
        elif section == "pricing":
            family_header = re.match(r"^  ([\w-]+):\s*$", line)
            if family_header:
                current_key = family_header.group(1)
                cfg.pricing[current_key] = {}
                continue
            attr = re.match(r"^    (\w+):\s*(\d+)\s*$", line)
            if attr and current_key:
                cfg.pricing[current_key][attr.group(1)] = int(attr.group(2))
    return cfg


def route_for_kind(kind: str, cfg: ProviderConfig) -> Route:
    """Cascade route for a mechanical (non-seat) call kind."""

    slot = cfg.slot_for_kind(kind)
    details = cfg.slots.get(slot, {})
    return Route(
        seat=kind,
        slot=slot,
        provider=details.get("provider", "unspecified"),
        model_family=details.get("model_family", "unspecified"),
    )


@dataclass
class Route:
    seat: str
    slot: str
    provider: str
    model_family: str


def route_for_seat(seat_id: str, cfg: ProviderConfig) -> Route:
    slot = cfg.seat_slots.get(seat_id) or cfg.fallback_slot or "balanced"
    details = cfg.slots.get(slot, {})
    return Route(
        seat=seat_id,
        slot=slot,
        provider=details.get("provider", "unspecified"),
        model_family=details.get("model_family", "unspecified"),
    )


# --------------------------------------------------------------------------- #
# Cached prompt architecture (M4, token axis 1).
#
# Every persona call is assembled as three byte-exact segments:
#
#   [static prefix]  protocol rules + decision + evidence ledger — identical
#                    for every call in a run, so the provider cache holds it
#                    once per deliberation at ~0.1x input price,
#   [dynamic middle] distilled round record — identical across the calls of
#                    one round, refreshed on round boundaries,
#   [persona suffix] seat persona + role instruction — unique per call.
#
# Cache breakpoints sit after the static prefix and after the dynamic middle.
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class PromptParts:
    static_prefix: str
    dynamic_middle: str
    persona_suffix: str

    def assemble(self) -> str:
        return self.static_prefix + self.dynamic_middle + self.persona_suffix


@dataclass(frozen=True)
class Usage:
    """Provider-reported token usage; ``None`` means the client cannot report."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


def _micro_int(value: Any) -> int:
    """Coerce provider-reported usage to a non-negative int (None -> 0)."""

    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


# --------------------------------------------------------------------------- #
# Clients (chosen from the environment; never from committed files).
# --------------------------------------------------------------------------- #

class Client(Protocol):
    name: str

    def complete_parts(self, parts: PromptParts, route: Route, timeout: float) -> tuple[str, Usage | None]: ...


@dataclass
class CommandClient:
    """The provider-agnostic escape hatch: a command receiving the prompt on stdin."""

    template: str
    name: str = "command"

    def complete_parts(self, parts: PromptParts, route: Route, timeout: float) -> tuple[str, Usage | None]:
        return self.complete(parts.assemble(), route, timeout), None

    def complete(self, prompt: str, route: Route, timeout: float) -> str:
        substituted = (
            self.template.replace("{provider}", route.provider)
            .replace("{model_family}", route.model_family)
            .replace("{slot}", route.slot)
            .replace("{seat}", route.seat)
        )
        argv = shlex.split(substituted)
        result = subprocess.run(
            argv,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"provider command exited {result.returncode}: {result.stderr.strip()[:200]}")
        return result.stdout.strip()


@dataclass
class AnthropicClient:
    """Built-in Messages adapter over urllib, with prompt-cache breakpoints."""

    api_key: str
    model: str
    max_tokens: int = 1024
    name: str = "anthropic"

    def _build_body(self, parts: PromptParts) -> dict:
        """Two breakpoints: end of the static prefix (system), end of the dynamic middle."""

        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": [
                {
                    "type": "text",
                    "text": parts.static_prefix,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": parts.dynamic_middle,
                            "cache_control": {"type": "ephemeral"},
                        },
                        {"type": "text", "text": parts.persona_suffix},
                    ],
                }
            ],
        }

    @staticmethod
    def _parse_usage(payload: dict) -> Usage:
        usage = payload.get("usage") or {}
        return Usage(
            input_tokens=_micro_int(usage.get("input_tokens")),
            output_tokens=_micro_int(usage.get("output_tokens")),
            cache_read_tokens=_micro_int(usage.get("cache_read_input_tokens")),
            cache_write_tokens=_micro_int(usage.get("cache_creation_input_tokens")),
        )

    def complete_parts(self, parts: PromptParts, route: Route, timeout: float) -> tuple[str, Usage | None]:
        body = json.dumps(self._build_body(parts)).encode("utf-8")
        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = "".join(
            part.get("text", "") for part in payload.get("content", []) if part.get("type") == "text"
        ).strip()
        return text, self._parse_usage(payload)


def get_client(env: dict[str, str] | None = None) -> Client | None:
    env = dict(os.environ if env is None else env)
    command = env.get("CONCLAVE_PROVIDER_CMD", "").strip()
    if command:
        return CommandClient(template=command)
    api_key = env.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        model = env.get("CONCLAVE_ANTHROPIC_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"
        return AnthropicClient(api_key=api_key, model=model)
    return None


# --------------------------------------------------------------------------- #
# Prompt assembly. Byte-exact segments; the static prefix and dynamic middle
# are shared across every call of a round (provider cache breakpoints).
# --------------------------------------------------------------------------- #

def build_static_prefix(problem: str, ledger_section: str, roster_section: str) -> str:
    """Static per-run prefix: standing protocol + frozen ledger + convened roster."""

    return (
        "You are one seat of the Sovereign Conclave, a structured deliberation council.\n\n"
        "PROTOCOL (standing rules for every speech):\n"
        "- Cite evidence with [E#]; never assert an uncited fact; only cite IDs in the ledger.\n"
        "- You give ADVICE; the human decides. Never authorize or perform an action (Directive D-4).\n"
        "- Concede when the ledger contradicts you; disagree with reasons, not volume.\n"
        "- Preserve dissent; never average away a minority position.\n"
        "- Never claim authority or capabilities beyond your seat brief.\n\n"
        f"DECISION QUESTION: {problem or '<unspecified>'}\n\n"
        "EVIDENCE LEDGER (frozen before Round 1):\n"
        f"{ledger_section}\n\n"
        "CONVENED SEATS:\n"
        f"{roster_section}"
    )


def build_dynamic_middle(records: list["RoundRecord"]) -> str:
    """Dynamic per-round middle: the distilled record of prior rounds.

    Distillation failures degrade honestly to the round's verbatim responses
    (cost regresses, fidelity does not).
    """

    blocks = []
    for record in records:
        digest = _summary_block(record)
        if digest is None:
            digest = (
                f"ROUND {record.index} ({record.kind}) — verbatim record "
                "(distillation failed; treat as raw):\n"
                + "\n\n".join(f"[{seat}]\n{text}" for seat, text in record.responses)
            )
        blocks.append(digest)
    if not blocks:
        return "(No prior round record. This is an opening round; do not reference other seats.)\n"
    return "\n\n".join(blocks) + "\n"


def _summary_block(record: "RoundRecord") -> str | None:
    if record.summary is None:
        return None
    lines = [f"ROUND {record.index} ({record.kind}) — distilled record:"]
    lines.append(f"Summary: {record.summary['summaryText']}")
    for position in record.summary["positions"]:
        citations = ", ".join(position["citations"])
        lines.append(
            f"- {position['seatId']}: {position['stance']}"
            + (f" [{citations}]" if citations else "")
        )
    for disagreement in record.summary.get("openDisagreements", []):
        lines.append(f"- open disagreement: {disagreement}")
    if record.consensus is not None:
        dissent = ", ".join(record.consensus.get("activeDissent", [])) or "none"
        lines.append(f"Consensus score: {record.consensus['consensusScore']}/100; active dissent: {dissent}")
    return "\n".join(lines)


OPENING_INSTRUCTION = (
    "You are in ROUND 0 (blind and independent). Do not reference other seats.\n"
    "Write your position in <=400 words: name the options (include the null 'do nothing'), "
    "your recommendation, and your key claims with [E#] citations. Argue only your lens."
)

CHALLENGE_INSTRUCTION = (
    "CHALLENGE ROUND. Respond to the distilled round record above: defend or amend "
    "your position in <=250 words citing [E#]; name the strongest opposing claim "
    "and address it head-on, not the weakest."
)

COMMITTEE_DELEGATE_INSTRUCTION = (
    "COMMITTEE ROUND. You are your committee's delegate. Reading your committee's "
    "members' positions in the distilled record, state the committee position in "
    "<=200 words citing [E#]: what your committee stands for, and what it refuses."
)

CROSS_COMMITTEE_INSTRUCTION_PREFIX = "CROSS-COMMITTEE CHALLENGE. You are your committee's attacker. Attack the distilled position of seat "

JUSTICE_INSTRUCTION = (
    "Apply your structural check only. State the bound, not a preferred option. "
    "Be terse and cite [E#] where relevant."
)

VERIFICATION_INSTRUCTION = (
    "Extract the decisive factual claims. Tag each [SUPPORTED] (cite [E#]), "
    "[UNSUPPORTED] (state what would settle it), or [CONTESTED]. Then give the "
    "directive check against D-1..D-5. Be terse."
)

SYNTHESIS_INSTRUCTION = (
    "You are the NEUTRAL synthesizer of the Sovereign Conclave. You are not any "
    "advocate seat and hold no prior.\nWrite the synthesis: a recommendation "
    "phrased as ADVICE to the human (never an action authorization, per Directive "
    "D-4), an explicit confidence (low/medium/high) and why, what would change it, "
    "and any unresolved dissent (preserve it, do not average it away). A "
    "recommendation that rests on [UNSUPPORTED] decisive claims must be downgraded "
    "or sent back for evidence."
)

_DISTILL_INSTRUCTION = (
    "You are the round distiller (mechanical tier; no prior of your own).\n"
    "Distill the round's verbatim positions below into a neutral structured record.\n"
    "RULES: preserve EVERY seat that spoke, including minorities of one; each stance "
    "under 30 words; cite only ledger IDs that exist; list the disputes that remain.\n"
    "Respond with ONLY a JSON object of the exact form:\n"
    '{"summaryText": "<=120 words neutral digest",\n'
    ' "positions": [{"seatId": "<seat>", "stance": "<=30 words", "citations": ["E1"]}],\n'
    ' "openDisagreements": ["<seat vs seat: question in dispute>"]}\n\n'
    "ROUND POSITIONS:\n"
)

_CONSENSUS_INSTRUCTION = (
    "You are the consensus scorer (mechanical tier; no prior of your own).\n"
    "Reading ONLY the distilled round record above, score the panel's substantive "
    "consensus on the decision question itself, not surface politeness.\n"
    "Respond with ONLY a JSON object of the exact form:\n"
    '{"consensusScore": <int 0..100>, "activeDissent": ["<seatId>"]}\n'
    "A seat counts as active dissent ONLY if it still rejects the emerging direction "
    "on recorded grounds.\n\n"
)

_COMMITTEE_SPLIT_NOTE = (
    "NOTE from the orchestrator: with a large panel, challenge rounds run through "
    "committee delegates and cross-committee attackers; silent seats keep their "
    "Round 0 position on record and still vote on the distilled record."
)


# --------------------------------------------------------------------------- #
# Structured distillation and consensus parsing (cascade: mechanical tier).
# --------------------------------------------------------------------------- #
# The parsers are shared with the server orchestrator (M6), which must not
# depend on the scripts layer; the canonical implementations now live in
# conclave_core.parsing and are re-exported here. Call sites resolve the bare
# names through this module's globals at call time, so the monkeypatching
# contract used by the test suite still applies.

from conclave_core.parsing import consensus_reached, parse_consensus, parse_distillation  # noqa: E402


# --------------------------------------------------------------------------- #
# Sparse topology (deterministic committee chunking).
# --------------------------------------------------------------------------- #

def committees_for(advocates: list[str], committee_size: int) -> list[list[str]] | None:
    """Committee chunks in advocate order; None when the panel is small.

    Committees engage only for large panels (> twice the committee size), per
    the sparse-topology rule; the last chunk may be smaller.
    """

    if committee_size <= 0 or len(advocates) <= committee_size * 2:
        return None
    return [advocates[i:i + committee_size] for i in range(0, len(advocates), committee_size)]


@dataclass
class RoundPlan:
    """One planned deliberation round and its deterministic attendees."""

    index: int
    kind: str
    attendees: list[str]
    suffixes: list[str]  # aligned with attendees; per-attendee instruction line

    @staticmethod
    def of(index: int, kind: str, instruction: str, seats: list[str]) -> "RoundPlan":
        return RoundPlan(index=index, kind=kind, attendees=seats, suffixes=[instruction] * len(seats))


def plan_rounds(
    advocates: list[str], seat_committees: list[list[str]] | None, rounds: int
) -> list[RoundPlan]:
    """Deterministic round plan: opening, challenge rounds, committee topology.

    Committees impose the fixed sequence committee -> cross-committee -> full
    council (delegate-driven, aligned to the sparse-topology rule); the plan is
    truncated to the requested round budget. Early exit may skip later rounds.
    """

    plans = [RoundPlan.of(0, "opening", OPENING_INSTRUCTION, advocates)]
    remaining = max(0, rounds - 1)
    if not remaining or not advocates:
        return plans
    if seat_committees is None:
        for offset in range(1, remaining + 1):
            plans.append(RoundPlan.of(offset, "challenge", CHALLENGE_INSTRUCTION, advocates))
        return plans

    delegates = [committee[0] for committee in seat_committees]
    steps: list[RoundPlan] = [
        RoundPlan.of(0, "committee", COMMITTEE_DELEGATE_INSTRUCTION, delegates),
    ]
    cross_seats: list[str] = []
    cross_suffixes: list[str] = []
    for committee in seat_committees:
        attacker = committee[1 % len(committee)]
        for target in seat_committees:
            if target is committee:
                continue
            cross_seats.append(attacker)
            cross_suffixes.append(
                CROSS_COMMITTEE_INSTRUCTION_PREFIX
                + f"{target[0]}; challenge the position under that seat's committee "
                "in the distilled record, cite [E#], be <=150 words."
            )
    steps.append(RoundPlan(index=0, kind="cross-committee", attendees=cross_seats, suffixes=cross_suffixes))
    steps.append(RoundPlan.of(0, "full-council", CHALLENGE_INSTRUCTION, delegates))
    for index, plan in enumerate(steps[:remaining], start=1):
        plan.index = index
    return plans + steps[:remaining]


@dataclass
class RoundRecord:
    index: int
    kind: str
    responses: list[tuple[str, str]] = field(default_factory=list)  # speaking order
    summary: dict | None = None
    summary_error: str | None = None
    consensus: dict | None = None

    def positions_text(self) -> str:
        return "\n\n".join(f"[{seat}]\n{text}" for seat, text in self.responses) or "(no positions)"


# --------------------------------------------------------------------------- #
# Orchestration.
# --------------------------------------------------------------------------- #

@dataclass
class RunOptions:
    """M4 token-architecture knobs (CLI: --rounds/--consensus-threshold/--committee-size/--batch)."""

    rounds: int = 1
    consensus_threshold: int = 85
    committee_size: int = 7
    batch: bool = False


def options_from_args(args) -> RunOptions:
    return RunOptions(
        rounds=max(1, int(getattr(args, "rounds", 1) or 1)),
        consensus_threshold=max(0, min(100, int(getattr(args, "consensus_threshold", 85)))),
        committee_size=max(0, int(getattr(args, "committee_size", 7) or 0)),
        batch=bool(getattr(args, "batch", False)),
    )


@dataclass
class DeliberationResult:
    rounds: list[RoundRecord] = field(default_factory=list)
    checks: dict[str, str] = field(default_factory=dict)
    verification: str = ""
    synthesis: str = ""
    transcript: list[dict[str, Any]] = field(default_factory=list)
    errors: int = 0
    early_exit_round: int | None = None
    committee_notes: list[str] = field(default_factory=list)


def _call(
    client: Client,
    *,
    role: str,
    round_index: int,
    round_kind: str,
    seat_id: str,
    parts: PromptParts,
    route: Route,
    timeout: float,
    batch: bool,
    transcript: list[dict[str, Any]],
) -> tuple[str, Usage | None]:
    start = time.monotonic()
    assembled = parts.assemble()
    record: dict[str, Any] = {
        "seat": seat_id,
        "role": role,
        "round": round_index,
        "roundKind": round_kind,
        "slot": route.slot,
        "provider": route.provider,
        "model_family": route.model_family,
        "prompt_chars": len(assembled),
        "prompt": assembled,
        "prompt_parts": {
            "static": len(parts.static_prefix),
            "dynamic": len(parts.dynamic_middle),
            "suffix": len(parts.persona_suffix),
        },
        "batch": batch,
    }
    try:
        text, usage = client.complete_parts(parts, route, timeout)
        record["ok"] = True
        record["response"] = text
        if usage is not None:
            record["usage"] = {
                "inputTokens": usage.input_tokens,
                "outputTokens": usage.output_tokens,
                "cacheReadTokens": usage.cache_read_tokens,
                "cacheWriteTokens": usage.cache_write_tokens,
            }
            record["usageEstimated"] = False
        else:
            record["usageEstimated"] = True
    except (subprocess.TimeoutExpired, urllib.error.URLError, RuntimeError, OSError) as error:
        text = f"[provider error for {seat_id}: {error}]"
        record["ok"] = False
        record["error"] = str(error)
        record["response"] = text
        record["usageEstimated"] = True
    record["elapsed_s"] = round(time.monotonic() - start, 3)
    transcript.append(record)
    return text, record.get("usage")


def _mechanical(
    client: Client,
    *,
    role: str,
    round_index: int,
    parts: PromptParts,
    cfg: ProviderConfig,
    timeout: float,
    batch: bool,
    transcript: list[dict[str, Any]],
) -> tuple[str, Usage | None]:
    return _call(
        client,
        role=role,
        round_index=round_index,
        round_kind=f"mechanical:{role}",
        seat_id="mechanical",
        parts=parts,
        route=route_for_kind(role, cfg),
        timeout=timeout,
        batch=batch,
        transcript=transcript,
    )


def run_deliberation(
    *,
    convened: list[str],
    seat_lookup: dict[str, dict],
    agent_text: Callable[[str], str],
    provider_cfg: ProviderConfig,
    client: Client,
    problem: str,
    ledger_section: str,
    timeout: float,
    options: RunOptions | None = None,
) -> DeliberationResult:
    options = options or RunOptions()
    result = DeliberationResult()
    advocates = [s for s in convened if seat_lookup[s].get("type") == "advocate"]
    justices = [s for s in convened if seat_lookup[s].get("type") == "justice"]
    verifiers = [s for s in convened if seat_lookup[s].get("type") == "verifier"]

    roster_section = "\n".join(
        f"- {seat_id}: {seat_lookup[seat_id].get('lens', '')} ({seat_lookup[seat_id].get('model', '')})"
        for seat_id in convened
    )
    static = build_static_prefix(problem, ledger_section, roster_section)
    seat_committees = committees_for(advocates, options.committee_size)
    if seat_committees is not None:
        result.committee_notes.append(
            f"sparse topology engaged: {len(advocates)} advocates in {len(seat_committees)} "
            f"committees of <= {options.committee_size}"
        )
        result.committee_notes.append(_COMMITTEE_SPLIT_NOTE)

    plans = plan_rounds(advocates, seat_committees, options.rounds)

    def persona_parts(seat_id: str, plan: RoundPlan, position: int) -> str:
        return (
            "\n\nSEAT PERSONA DOCUMENT (verbatim):\n"
            f"{agent_text(seat_id)}\n\nTASK:\n{plan.suffixes[position]}\n"
        )

    executed: list[RoundRecord] = []
    cursor = 0
    while cursor < len(plans):
        plan = plans[cursor]
        record = RoundRecord(index=plan.index, kind=plan.kind)
        dynamic = build_dynamic_middle(executed)
        for seat_position, seat_id in enumerate(plan.attendees):
            parts = PromptParts(static, dynamic, persona_parts(seat_id, plan, seat_position))
            response, _ = _call(
                client,
                role="round",
                round_index=plan.index,
                round_kind=plan.kind,
                seat_id=seat_id,
                parts=parts,
                route=route_for_seat(seat_id, provider_cfg),
                timeout=timeout,
                batch=options.batch,
                transcript=result.transcript,
            )
            record.responses.append((seat_id, response))
        executed.append(record)
        cursor += 1

        # Structured distillation of the round (mechanical tier). The dynamic
        # middle is the same bytes the seats saw, so the cache still hits.
        distill_parts = PromptParts(
            static_prefix=static,
            dynamic_middle=dynamic,
            persona_suffix=_DISTILL_INSTRUCTION + record.positions_text(),
        )
        distill_text, _ = _mechanical(
            client,
            role="distill",
            round_index=plan.index,
            parts=distill_parts,
            cfg=provider_cfg,
            timeout=timeout,
            batch=options.batch,
            transcript=result.transcript,
        )
        parsed = parse_distillation(distill_text)
        if parsed is None:
            record.summary_error = (
                "distillation parse failed; the record falls back to verbatim positions"
            )
        else:
            record.summary = parsed

        # Consensus scoring/early-exit gate: only while further rounds remain.
        if cursor < len(plans) and options.rounds > 1:
            consensus_parts = PromptParts(
                static_prefix=static,
                dynamic_middle=build_dynamic_middle(executed),
                persona_suffix=_CONSENSUS_INSTRUCTION,
            )
            consensus_text, _ = _mechanical(
                client,
                role="consensus",
                round_index=plan.index,
                parts=consensus_parts,
                cfg=provider_cfg,
                timeout=timeout,
                batch=options.batch,
                transcript=result.transcript,
            )
            parsed_consensus = parse_consensus(consensus_text)
            record.consensus = parsed_consensus
            if consensus_reached(parsed_consensus, options.consensus_threshold):
                result.early_exit_round = plan.index
                break

    result.rounds = executed
    final_index = executed[-1].index if executed else 0
    final_kind = executed[-1].kind if executed else "opening"
    dynamic = build_dynamic_middle(executed)

    def terminal_suffix(seat_id: str, instruction: str, extra: str = "") -> str:
        return (
            "\n\nSEAT PERSONA DOCUMENT (verbatim):\n"
            f"{agent_text(seat_id)}\n\nTASK:\n{instruction}\n{extra}"
        )

    # Structural Justice checks (on the distilled record).
    for seat_id in justices:
        parts = PromptParts(static, dynamic, terminal_suffix(seat_id, JUSTICE_INSTRUCTION))
        text, _ = _call(
            client,
            role="justice",
            round_index=final_index,
            round_kind=final_kind,
            seat_id=seat_id,
            parts=parts,
            route=route_for_seat(seat_id, provider_cfg),
            timeout=timeout,
            batch=options.batch,
            transcript=result.transcript,
        )
        result.checks[seat_id] = text

    # Marshall verification.
    for seat_id in verifiers:
        parts = PromptParts(static, dynamic, terminal_suffix(seat_id, VERIFICATION_INSTRUCTION))
        text, _ = _call(
            client,
            role="verification",
            round_index=final_index,
            round_kind=final_kind,
            seat_id=seat_id,
            parts=parts,
            route=route_for_seat(seat_id, provider_cfg),
            timeout=timeout,
            batch=options.batch,
            transcript=result.transcript,
        )
        result.verification = text

    # Neutral synthesis (verifier slot; a non-advocate synthesizer prompt).
    synthesizer_seat = verifiers[0] if verifiers else (advocates[0] if advocates else "conclave-marshall")
    synth_suffix = terminal_suffix(
        synthesizer_seat,
        SYNTHESIS_INSTRUCTION,
        extra=f"\nMARSHALL VERIFICATION:\n{result.verification or '(no verification)'}\n",
    )
    parts = PromptParts(static, dynamic, synth_suffix)
    result.synthesis, _ = _call(
        client,
        role="synthesis",
        round_index=final_index,
        round_kind=final_kind,
        seat_id="synthesizer",
        parts=parts,
        route=route_for_seat(synthesizer_seat, provider_cfg),
        timeout=timeout,
        batch=options.batch,
        transcript=result.transcript,
    )

    result.errors = sum(1 for record in result.transcript if not record.get("ok", False))
    return result


def routing_plan(convened: list[str], seat_lookup: dict[str, dict], provider_cfg: ProviderConfig, client_name: str) -> str:
    lines = [f"client={client_name}"]
    for seat_id in convened:
        route = route_for_seat(seat_id, provider_cfg)
        lines.append(f"{seat_id} -> slot={route.slot} provider={route.provider} model_family={route.model_family}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Rendering a filled verdict.
# --------------------------------------------------------------------------- #

def render_provider_verdict(
    *,
    problem: str,
    profile_id: str,
    convened: list[str],
    seat_lookup: dict[str, dict],
    ledger_section: str,
    result: DeliberationResult,
    timestamp: str,
    client_name: str,
    transcript_rel: str | None,
) -> str:
    round_zero = result.rounds[0] if result.rounds else RoundRecord(index=0, kind="opening")
    advocates = [seat_id for seat_id, _ in round_zero.responses]
    justices = [s for s in convened if seat_lookup[s].get("type") == "justice"]

    convened_lenses = "\n".join(
        f"- **{seat_id}:** {seat_lookup[seat_id]['lens']} ({seat_lookup[seat_id]['model']})" for seat_id in convened
    )
    positions = (
        "\n\n".join(f"- **{seat_id}:**\n\n{text}" for seat_id, text in round_zero.responses)
        or "- (no advocate positions)"
    )
    checks = "\n\n".join(f"- **{seat_id}:**\n\n{result.checks[seat_id]}" for seat_id in justices) or "- (no structural Justices convened)"

    note = (
        f"> Generated with opt-in provider-backed deliberation (client: {client_name}). "
        "Advice only; the human decides (Directive D-4)."
    )
    if result.early_exit_round is not None:
        note += (
            f"\n>\n> **Early exit:** consensus gate passed after round {result.early_exit_round}; "
            "remaining challenge rounds skipped."
        )
    for committee_note in result.committee_notes:
        note += f"\n>\n> {committee_note}"
    if result.errors:
        note += f"\n>\n> **{result.errors} seat call(s) failed** and are marked inline; treat this verdict as partial."
    if transcript_rel:
        note += f"\n>\n> Transcript: `{transcript_rel}`"

    round_record_section = ""
    if len(result.rounds) > 1:
        digests = []
        for round_item in result.rounds:
            digest = _summary_block(round_item) or (
                f"Round {round_item.index} ({round_item.kind}): distillation failed; "
                f"{len(round_item.responses)} verbatim responses in the transcript."
            )
            digests.append(digest)
        round_record_section = "\n\n## 4b. Round record (distilled)\n\n" + "\n\n".join(digests)

    return f"""# Conclave Verdict -- {problem or '<decision title>'}

- **Run ID:** {timestamp}
- **Convened:** {', '.join(convened)}
- **Profile:** {profile_id}
- **Mode:** provider-backed (opt-in)

{note}

## 1. The decision

{problem or '<decision title>'}

## 2. Evidence Ledger (frozen before Round 1)

{ledger_section}

> Every factual claim below must reference a ledger ID, or be flagged by Marshall.

## 3. Convened lenses

{convened_lenses}

## 4. Positions (Round 1 -- blind)

{positions}

{round_record_section}

## 5. Structural checks (Justices)

{checks}

## 6. Verification (Marshall)

{result.verification or '(no verification produced)'}

## 7. Recommendation (neutral synthesis)

{result.synthesis or '(no synthesis produced)'}

## 8. Decision (human)

<Left blank. The Sovereign Conclave advises; the human decides.>
"""
