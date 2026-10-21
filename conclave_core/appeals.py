"""M5 appeal engine: triggers, windows, caps, and the escalation ladder.

Roadmap contract (v0.2.0 M5):

- Triggers: T1 new evidence (Marshall screens materiality), T2 procedural
  violation (proven mechanically against the DAG -> auto-granted), T3 dissent
  weight share >= 30% (automatic, immediate, no gate). T4 stakeholder petition
  is explicitly deferred to v0.3.
- Ladder: Tier A re-deliberation with expanded context, Tier B adversarial
  appellate panel (disjoint draw, dissent steelman in scope), Tier C human
  arbiter as the final terminus: a human closes the case.
- Anti-abuse: one appeal per trigger class per case by default; Tier B
  convening requires a granted appeal (admitted T1 screening, proven T2
  checks, or automatic T3).
- Every appeal artifact links the original DeliberationManifest CID.

This module is pure logic over a decoded artifact store (a bundle directory);
it never mutates bundles. The CLI layer (scripts/conclave_runner.py) calls the
engine and persists artifacts through the emitter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .artifacts import (
    artifact_cid,
    make_appeal,
    make_appeal_screening,
    make_appeal_verdict,
    make_arbiter_ruling,
)
from .cbor import decode
from .cid import Cid, parse
from .verifier import verify_bundle

TRIGGERS = ("T1", "T2", "T3")
OUTCOMES = ("affirm", "reverse", "remand")
DEFAULT_WEIGHT_SHARE_MICRO = 300_000  # T3: dissent weight share >= 30%
DEFAULT_APPEAL_CAP_PER_TRIGGER = 1

_T2_REVERSE_PROBLEMS = ("signature-chain", "log:")


class AppealError(Exception):
    """A filing or adjudication violates the roadmap's anti-abuse gates."""


def decode_store(bundle_dir: Path) -> dict[Cid, dict]:
    """Decode every artifact file in a bundle directory, keyed by its CID."""

    store: dict[Cid, dict] = {}
    artifacts_dir = Path(bundle_dir) / "artifacts"
    for path in sorted(artifacts_dir.glob("*.cbor")):
        try:
            artifact = decode(path.read_bytes())
        except Exception as exc:  # decode errors are verifier problems, not engine crashes
            raise ValueError(f"{path.name}: cannot decode artifact: {exc}") from exc
        store[artifact_cid(artifact)] = artifact
    return store


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(str(text).replace("Z", "+00:00"))


def weight_share_micro(verdict: dict, resolve_dissent) -> int | None:
    """T3 share math: dissenting voting weight over total, in micro-share.

    ``resolve_dissent`` maps a dissent CID to its Dissent artifact (or None
    when the link does not resolve). Seat weights come from the verdict's
    votes; dissents whose seats hold no recorded vote are ignored. Empty
    or weightless electorates return None (share unknown, never auto-T3).
    """

    if not isinstance(verdict, dict):
        return None
    weights = {
        vote["seatId"]: int(vote["weightMicro"])
        for vote in verdict.get("votes", [])
        if isinstance(vote, dict) and "seatId" in vote
    }
    total = sum(weights.values())
    if total <= 0:
        return None
    dissent_seats = set()
    for link in verdict.get("dissents") or []:
        dissent = resolve_dissent(link)
        if isinstance(dissent, dict) and dissent.get("seatId"):
            dissent_seats.add(str(dissent["seatId"]))
    dissenting_weight = sum(weights[seat] for seat in dissent_seats if seat in weights)
    return dissenting_weight * 1_000_000 // total


@dataclass
class AppealCase:
    """Read-only view of one case bundle for appeal decisioning."""

    bundle_dir: Path
    store: dict[Cid, dict] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.store = decode_store(self.bundle_dir)
        self.config = json.loads((Path(self.bundle_dir) / "bundle.json").read_text(encoding="utf-8"))
        self.manifest_cid = parse(self.config["manifestCid"])
        self.manifest = self._resolve_manifest(self.manifest_cid)
        self.verdict_cid = self.manifest.get("verdict")
        self.verdict = self.store.get(self.verdict_cid) if isinstance(self.verdict_cid, Cid) else None
        self.protocol_params = self._protocol_params()
        self.window_days = (
            int(self.protocol_params.get("appealDefaultWindowDays", 30))
            if isinstance(self.protocol_params, dict)
            else 30
        )

    @property
    def appeals(self) -> list[tuple[Cid, dict]]:
        """Appeal artifacts currently visible in the decoded store."""

        return [
            (cid, artifact)
            for cid, artifact in self.store.items()
            if artifact.get("type") == "Appeal"
        ]

    def _resolve_manifest(self, manifest_cid: Cid) -> dict:
        manifest = self.store.get(manifest_cid)
        if not isinstance(manifest, dict):
            raise ValueError(f"manifest {manifest_cid} is missing from the bundle")
        return manifest

    def _protocol_params(self) -> dict | None:
        link = self.manifest.get("protocolParams")
        return self.store.get(link) if isinstance(link, Cid) else None

    def validate_bundle(self) -> list[str]:
        """Public-verification pass; T2 gates on whatever it finds."""

        problems, _summary = verify_bundle(Path(self.bundle_dir))
        return list(problems)

    # ---- standing checks ---------------------------------------------------

    def trigger_count(self, trigger: str) -> int:
        return sum(1 for _, artifact in self.appeals if artifact.get("trigger") == trigger)

    def can_file(self, trigger: str, cap: int = DEFAULT_APPEAL_CAP_PER_TRIGGER) -> tuple[bool, str]:
        if trigger not in TRIGGERS:
            return False, f"unsupported trigger {trigger!r} (T4 stakeholder petitions defer to v0.3)"
        if self.trigger_count(trigger) >= cap:
            return False, (
                f"anti-abuse cap reached: {cap} appeal(s) per trigger class already filed "
                f"for trigger {trigger}"
            )
        return True, ""

    def dissent_weight_share_micro(self) -> int | None:
        return weight_share_micro(self.verdict, self.store.get)

    def window_open(self, trigger: str, filed_at: str, window_days: int | None = None) -> tuple[bool, str]:
        """T2 violations have no time limit; T1/T3 file inside the window."""

        if trigger == "T2":
            return True, ""
        if not isinstance(self.verdict, dict):
            return False, "the bundle carries no verdict yet; nothing to appeal"
        issued = parse_utc(self.verdict["issuedAt"])
        filed = parse_utc(filed_at)
        days = int(window_days if window_days is not None else self.window_days)
        deadline = issued + timedelta(days=days)
        if filed > deadline:
            return False, (
                f"outside the finality window: verdict issued {issued:%Y-%m-%d}, "
                f"window {days} days, filed {filed:%Y-%m-%d}"
            )
        return True, ""

    def t3_auto_scheduled(self, share_micro: int | None = None) -> bool:
        share = self.dissent_weight_share_micro() if share_micro is None else share_micro
        return share is not None and share >= DEFAULT_WEIGHT_SHARE_MICRO

    # ---- state transitions (return artifacts; caller persists) -------------

    def file_appeal(
        self,
        *,
        trigger: str,
        grounds: str,
        filed_by: str,
        filed_at: str,
        supplement_ledger: Cid | None = None,
        proven_violation_checks: list[str] | None = None,
        window_days: int | None = None,
        cap: int = DEFAULT_APPEAL_CAP_PER_TRIGGER,
    ) -> dict:
        allowed, reason = self.can_file(trigger, cap)
        if not allowed:
            raise AppealError(reason)
        window_ok, window_reason = self.window_open(trigger, filed_at, window_days)
        if not window_ok:
            raise AppealError(window_reason)
        if trigger == "T2" and not proven_violation_checks:
            raise AppealError(
                "T2 requires mechanically proven procedural violations: run the "
                "verifier over the bundle and attach its findings"
            )
        if trigger == "T1" and supplement_ledger is None:
            raise AppealError("T1 requires the material evidence as a supplement EvidenceLedger")
        effective_window = self.window_days if window_days is None else int(window_days)
        return make_appeal(
            verdict=self.verdict_cid,
            case_manifest=self.manifest_cid,
            trigger=trigger,
            grounds=grounds,
            filed_by=filed_by,
            filed_at=filed_at,
            supplement_ledger=supplement_ledger,
            proven_violation_checks=proven_violation_checks,
            window_days=effective_window,
        )

    def appeal_granted(self, appeal_cid: Cid) -> tuple[bool, str]:
        """Which gate applies: admitted T1 screening / proven T2 / automatic T3."""

        appeal_cid = _as_cid(appeal_cid)
        appeal = self.store.get(appeal_cid)
        if not isinstance(appeal, dict):
            return False, "appeal artifact not found"
        trigger = appeal.get("trigger")
        if trigger == "T2":
            if appeal.get("provenViolationChecks"):
                return True, "T2 proven mechanically against the DAG"
            return False, "T2 with no proven violation checks"
        if trigger == "T3":
            if self.t3_auto_scheduled():
                return True, "T3 automatic: dissent weight share above threshold"
            return False, "T3 share below threshold"
        if trigger == "T1":
            screenings = [
                artifact
                for artifact in self.store.values()
                if artifact.get("type") == "AppealScreening" and artifact.get("appeal") == appeal_cid
            ]
            if not screenings:
                return False, "T1 awaits Marshall screening"
            latest = max(
                screenings,
                key=lambda screening: (str(screening.get("screenedAt")), str(artifact_cid(screening))),
            )
            if latest.get("decision") == "admitted":
                return True, "T1 admitted by Marshall screening"
            return False, "T1 rejected by Marshall screening"
        return False, f"appeal trigger {trigger!r} unrecognised"

    def screen_appeal(
        self, *, appeal_cid: Cid, decision: str, screened_by: str, reasons: str, screened_at: str
    ) -> dict:
        if decision not in ("admitted", "rejected"):
            raise ValueError("screening decision must be 'admitted' or 'rejected'")
        appeal_cid = _as_cid(appeal_cid)
        if self.store.get(appeal_cid, {}).get("trigger") != "T1":
            raise ValueError("only T1 appeals go through Marshall materiality screening")
        return make_appeal_screening(
            appeal=appeal_cid,
            decision=decision,
            screened_by=screened_by,
            reasons=reasons,
            screened_at=screened_at,
        )

    def adjudicate_appeal(
        self,
        *,
        appeal_cid: Cid,
        tier: str,
        outcome: str,
        scope: str,
        rationale: str,
        reviewed_verdict: Cid | None = None,
        panel_seats: list[str] | None = None,
        recorded_at: str,
    ) -> dict:
        if tier not in ("A", "B"):
            raise ValueError("tier must be 'A' (re-deliberation) or 'B' (appellate panel)")
        if outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}")
        appeal_cid = _as_cid(appeal_cid)
        granted, gate = self.appeal_granted(appeal_cid)
        if not granted:
            raise AppealError(f"Tier {tier} convening requires a granted appeal; gate says: {gate}")
        return make_appeal_verdict(
            appeal=appeal_cid,
            tier=tier,
            outcome=outcome,
            scope=scope,
            rationale=rationale,
            original_verdict=self.verdict_cid,
            reviewed_verdict=reviewed_verdict,
            recorded_at=recorded_at,
            panel_seats=panel_seats,
        )

    def arbitrate_appeal(
        self, *, appeal_cid: Cid, arbiter: str, disposition: str, ruling: str, ruled_at: str
    ) -> dict:
        if disposition not in ("affirm", "reverse", "remand", "dismiss"):
            raise ValueError("disposition must be one of affirm/reverse/remand/dismiss")
        appeal_cid = _as_cid(appeal_cid)
        if appeal_cid not in {cid for cid, _ in self.appeals}:
            raise ValueError("ruling references an appeal not filed on this case")
        return make_arbiter_ruling(
            appeal=appeal_cid,
            arbiter=arbiter,
            disposition=disposition,
            ruling=ruling,
            ruled_at=ruled_at,
        )

    def allowed_tier_b_panel(self, roster_seats: list[str], size: int = 3) -> list[str]:
        """Deterministic disjoint appellate draw: roster order minus convened."""

        if size < 1:
            raise ValueError("appellate draw size must be at least 1")
        convened_seats = self._convened_history()
        pick = [seat for seat in roster_seats if seat not in convened_seats][:size]
        if len(pick) < size:
            raise ValueError(
                "roster too small for a disjoint appellate draw of size "
                f"{size}; only {len(pick)} seats remain"
            )
        return pick

    def _convened_history(self) -> set[str]:
        seats: set[str] = set()
        for _, artifact in self.store.items():
            if artifact.get("type") == "Round" and artifact.get("participants"):
                seats.update(
                    participant
                    for participant in artifact["participants"]
                    if isinstance(participant, str)
                )
        return seats


def mechanical_outcome_suggestion(problems: list[str]) -> str:
    """T2 disposition rule: verdict-breaking integrity failures -> reverse."""

    for problem in problems:
        if any(problem.startswith(prefix) for prefix in _T2_REVERSE_PROBLEMS):
            return "reverse"
    return "remand"


def _as_cid(value: Any) -> Cid:
    if isinstance(value, Cid):
        return value
    return parse(str(value))
