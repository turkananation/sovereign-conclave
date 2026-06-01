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


def parse_provider_config(text: str) -> ProviderConfig:
    cfg = ProviderConfig()
    section: str | None = None
    current_slot: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z]", line):
            section = line.split(":", 1)[0].strip()
            current_slot = None
            continue
        if section == "defaults":
            match = re.match(r"^\s+(\w+):\s*(\S+)\s*$", line)
            if match:
                if match.group(1) == "fallback_slot":
                    cfg.fallback_slot = match.group(2)
                elif match.group(1) == "key_source":
                    cfg.key_source = match.group(2)
        elif section == "slots":
            slot_header = re.match(r"^  ([A-Za-z][\w-]*):\s*$", line)
            if slot_header:
                current_slot = slot_header.group(1)
                cfg.slots[current_slot] = {}
                continue
            attr = re.match(r"^    (\w+):\s*(\S+)\s*$", line)
            if attr and current_slot:
                cfg.slots[current_slot][attr.group(1)] = attr.group(2)
        elif section == "seat_slots":
            seat = re.match(r"^  (conclave-[a-z0-9-]+):\s*([A-Za-z][\w-]*)\s*$", line)
            if seat:
                cfg.seat_slots[seat.group(1)] = seat.group(2)
    return cfg


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
# Clients (chosen from the environment; never from committed files).
# --------------------------------------------------------------------------- #

class Client(Protocol):
    name: str

    def complete(self, prompt: str, route: Route, timeout: float) -> str: ...


@dataclass
class CommandClient:
    template: str
    name: str = "command"

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
    api_key: str
    model: str
    max_tokens: int = 1024
    name: str = "anthropic"

    def complete(self, prompt: str, route: Route, timeout: float) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8")
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
        parts = payload.get("content", [])
        return "".join(part.get("text", "") for part in parts if part.get("type") == "text").strip()


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
# Prompts (faithful to SKILL.md; compact).
# --------------------------------------------------------------------------- #

def _round1_prompt(persona: str, problem: str, ledger_section: str) -> str:
    return (
        f"{persona}\n\n"
        "You are deliberating in ROUND 1 (blind and independent). Do not reference other seats.\n\n"
        f"DECISION: {problem or '<unspecified>'}\n\n"
        "EVIDENCE LEDGER (frozen; cite E# for every factual claim, only IDs that exist):\n"
        f"{ledger_section}\n\n"
        "Write your Round 1 position in <=400 words: name the options (include the null 'do nothing'), "
        "your recommendation, and your key claims with [E#] citations. Argue only your lens."
    )


def _justice_prompt(persona: str, problem: str, ledger_section: str, positions: str) -> str:
    return (
        f"{persona}\n\n"
        f"DECISION: {problem or '<unspecified>'}\n\n"
        f"EVIDENCE LEDGER:\n{ledger_section}\n\n"
        f"ROUND 1 POSITIONS:\n{positions}\n\n"
        "Apply your structural check only. State the bound, not a preferred option. Be terse and cite E# where relevant."
    )


def _verification_prompt(persona: str, problem: str, ledger_section: str, positions: str) -> str:
    return (
        f"{persona}\n\n"
        f"DECISION: {problem or '<unspecified>'}\n\n"
        f"EVIDENCE LEDGER:\n{ledger_section}\n\n"
        f"ROUND 1 POSITIONS:\n{positions}\n\n"
        "Extract the decisive factual claims. Tag each [SUPPORTED] (cite E#), [UNSUPPORTED] "
        "(state what would settle it), or [CONTESTED]. Then give the directive check against D-1..D-5. Be terse."
    )


def _synthesis_prompt(problem: str, ledger_section: str, positions: str, verification: str) -> str:
    return (
        "You are the NEUTRAL synthesizer of the Sovereign Conclave. You are not any advocate seat and hold no prior.\n\n"
        f"DECISION: {problem or '<unspecified>'}\n\n"
        f"EVIDENCE LEDGER:\n{ledger_section}\n\n"
        f"ROUND 1 POSITIONS:\n{positions}\n\n"
        f"MARSHALL VERIFICATION:\n{verification}\n\n"
        "Write the synthesis: a recommendation phrased as ADVICE to the human (never an action authorization, "
        "per Directive D-4), an explicit confidence (low/medium/high) and why, what would change it, and any "
        "unresolved dissent (preserve it, do not average it away). A recommendation that rests on [UNSUPPORTED] "
        "decisive claims must be downgraded or sent back for evidence."
    )


# --------------------------------------------------------------------------- #
# Orchestration.
# --------------------------------------------------------------------------- #

@dataclass
class DeliberationResult:
    round1: dict[str, str] = field(default_factory=dict)
    checks: dict[str, str] = field(default_factory=dict)
    verification: str = ""
    synthesis: str = ""
    transcript: list[dict[str, Any]] = field(default_factory=list)
    errors: int = 0


def _call(
    client: Client,
    role: str,
    seat_id: str,
    prompt: str,
    route: Route,
    timeout: float,
    transcript: list[dict[str, Any]],
) -> str:
    start = time.monotonic()
    record: dict[str, Any] = {
        "seat": seat_id,
        "role": role,
        "slot": route.slot,
        "provider": route.provider,
        "model_family": route.model_family,
        "prompt_chars": len(prompt),
    }
    try:
        text = client.complete(prompt, route, timeout)
        record["ok"] = True
        record["response"] = text
    except (subprocess.TimeoutExpired, urllib.error.URLError, RuntimeError, OSError) as error:
        text = f"[provider error for {seat_id}: {error}]"
        record["ok"] = False
        record["error"] = str(error)
        record["response"] = text
    record["elapsed_s"] = round(time.monotonic() - start, 3)
    transcript.append(record)
    return text


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
) -> DeliberationResult:
    result = DeliberationResult()
    advocates = [s for s in convened if seat_lookup[s].get("type") == "advocate"]
    justices = [s for s in convened if seat_lookup[s].get("type") == "justice"]
    verifiers = [s for s in convened if seat_lookup[s].get("type") == "verifier"]

    # Round 1: advocates, blind and independent.
    for seat_id in advocates:
        route = route_for_seat(seat_id, provider_cfg)
        prompt = _round1_prompt(agent_text(seat_id), problem, ledger_section)
        result.round1[seat_id] = _call(client, "round1", seat_id, prompt, route, timeout, result.transcript)

    positions = "\n\n".join(f"[{s}]\n{result.round1[s]}" for s in advocates) or "(no advocate positions)"

    # Structural Justice checks.
    for seat_id in justices:
        route = route_for_seat(seat_id, provider_cfg)
        prompt = _justice_prompt(agent_text(seat_id), problem, ledger_section, positions)
        result.checks[seat_id] = _call(client, "justice", seat_id, prompt, route, timeout, result.transcript)

    # Marshall verification.
    for seat_id in verifiers:
        route = route_for_seat(seat_id, provider_cfg)
        prompt = _verification_prompt(agent_text(seat_id), problem, ledger_section, positions)
        result.verification = _call(client, "verification", seat_id, prompt, route, timeout, result.transcript)

    # Neutral synthesis (verifier slot, but a non-advocate synthesizer prompt).
    synth_route = route_for_seat(verifiers[0] if verifiers else (advocates[0] if advocates else "conclave-marshall"), provider_cfg)
    synth_prompt = _synthesis_prompt(problem, ledger_section, positions, result.verification or "(no verification)")
    result.synthesis = _call(client, "synthesis", "synthesizer", synth_prompt, synth_route, timeout, result.transcript)

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
    advocates = [s for s in convened if seat_lookup[s].get("type") == "advocate"]
    justices = [s for s in convened if seat_lookup[s].get("type") == "justice"]

    convened_lenses = "\n".join(
        f"- **{seat_id}:** {seat_lookup[seat_id]['lens']} ({seat_lookup[seat_id]['model']})" for seat_id in convened
    )
    positions = "\n\n".join(f"- **{seat_id}:**\n\n{result.round1[seat_id]}" for seat_id in advocates) or "- (no advocate positions)"
    checks = "\n\n".join(f"- **{seat_id}:**\n\n{result.checks[seat_id]}" for seat_id in justices) or "- (no structural Justices convened)"

    note = (
        f"> Generated with opt-in provider-backed deliberation (client: {client_name}). "
        "Advice only; the human decides (Directive D-4)."
    )
    if result.errors:
        note += f"\n>\n> **{result.errors} seat call(s) failed** and are marked inline; treat this verdict as partial."
    if transcript_rel:
        note += f"\n>\n> Transcript: `{transcript_rel}`"

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

## 5. Structural checks (Justices)

{checks}

## 6. Verification (Marshall)

{result.verification or '(no verification produced)'}

## 7. Recommendation (neutral synthesis)

{result.synthesis or '(no synthesis produced)'}

## 8. Decision (human)

<Left blank. The Sovereign Conclave advises; the human decides.>
"""
