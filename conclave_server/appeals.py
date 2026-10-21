"""M6 appeal bridge: the M5 engine runs over a materialized case bundle.

The appeal engine (``conclave_core.appeals.AppealCase``) is a read-only
decision-maker over bundle directories; the server materializes the case's
current store subset into a temp dir, runs the trigger gates (T1 evidence
screening, T2 mechanically proven violations via the verifier, capped T3),
and persists the returned artifacts through the store: ingest, identity-key
signature, transparency-log leaf + STH growth, and a re-tracked session row
so the next materialization carries the full appeal history.

Tier B/arbiter flows stay CLI-driven in v0.2 (documented deviation); the
server exposes petition filing and Marshall screening, matching the
roadmap's endpoint verbs.
"""

from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path
from typing import Any

from conclave_core.appeals import AppealCase, AppealError
from conclave_core.artifacts import artifact_cid, utc_now
from conclave_core.ledger import supplement_ledger
from conclave_core.keystore import IDENTITY_SEED_FILE, load_or_create_seed
from conclave_core.signing import (
    DOMAIN_APPEAL_PETITION,
    DOMAIN_APPEAL_SCREENING,
    make_signature_signed,
)

from .materialize import materialize_case
from .store import ArtifactStore

# artifacts that enter the transparency log (roadmap M5 item 4; v0.2 logs
# the appeal lifecycle and every verdict-bearing artifact)
LOGGED_TYPES = (
    "Verdict",
    "Dissent",
    "EvidenceLedger",
    "Appeal",
    "AppealScreening",
    "AppealVerdict",
    "ArbiterRuling",
)


class AppealBridge:
    """Petition + screening against persisted cases under one lock."""

    def __init__(self, store: ArtifactStore, keys_dir: Path) -> None:
        self.store = store
        self.keys_dir = Path(keys_dir)
        self._bridge_lock = threading.Lock()

    # -- public surface -------------------------------------------------------

    def file_petition(
        self,
        case_ref: str,
        *,
        trigger: str,
        grounds: str,
        filed_by: str,
        documents: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """File one appeal (T1 with evidence, T2 with proven violations)."""

        with self._bridge_lock:
            return self._file_petition_locked(case_ref, trigger, grounds, filed_by, documents)

    def screen_petition(
        self, case_ref: str, *, appeal_cid: str, decision: str, screened_by: str, reasons: str
    ) -> dict[str, Any]:
        """Record a Marshall materiality screening for a T1 appeal."""

        with self._bridge_lock:
            return self._screen_petition_locked(case_ref, appeal_cid, decision, screened_by, reasons)

    # -- stages -----------------------------------------------------------------

    def _file_petition_locked(
        self,
        case_ref: str,
        trigger: str,
        grounds: str,
        filed_by: str,
        documents: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        petitioned_at = utc_now()
        with tempfile.TemporaryDirectory(prefix="conclave-appeal-") as tmp:
            bundle = materialize_case(
                self.store, self.keys_dir, case_ref, Path(tmp) / "case"
            )
            case = AppealCase(bundle)
            supplement_cid = None
            supplement = None
            if trigger == "T1":
                if not documents:
                    raise AppealError("T1 requires the material evidence as ledger documents")
                problems = case.validate_bundle()
                if problems:
                    raise AppealError(
                        "the case bundle does not verify; T1 appeals clean up the record first: "
                        + "; ".join(problems)
                    )
                ledger = self.store.get(case.manifest["evidenceLedger"])
                if not isinstance(ledger, dict):
                    raise AppealError("the case's frozen evidence ledger is missing")
                supplement = supplement_ledger(ledger, case.manifest["evidenceLedger"], documents)
                supplement_cid = artifact_cid(supplement)
            proven_checks = None
            if trigger == "T2":
                proven_checks = list(case.validate_bundle())
            appeal = case.file_appeal(
                trigger=trigger,
                grounds=grounds,
                filed_by=filed_by,
                filed_at=petitioned_at,
                supplement_ledger=supplement_cid,
                proven_violation_checks=proven_checks,
            )

            # persist: supplement + appeal + identity signature; logged types grow the log
            artifacts: list[dict] = []
            if supplement is not None:
                artifacts.append(supplement)
            artifacts.append(appeal)
            identity_seed = load_or_create_seed(self.keys_dir / IDENTITY_SEED_FILE)
            petition_cid = artifact_cid(appeal)
            artifacts.append(
                make_signature_signed(
                    seed=identity_seed, domain=DOMAIN_APPEAL_PETITION,
                    payload=petition_cid, signed_at=petitioned_at,
                )
            )
            self._persist(case_ref, artifacts, petitioned_at)
            return {
                "caseRef": case_ref,
                "appealRef": str(petition_cid),
                "trigger": trigger,
                "supplementRef": str(supplement_cid) if supplement_cid else None,
                "provenViolations": proven_checks or None,
                "filedAt": petitioned_at,
            }

    def _screen_petition_locked(
        self, case_ref: str, appeal_cid: str, decision: str, screened_by: str, reasons: str
    ) -> dict[str, Any]:
        screened_at = utc_now()
        with tempfile.TemporaryDirectory(prefix="conclave-screen-") as tmp:
            bundle = materialize_case(
                self.store, self.keys_dir, case_ref, Path(tmp) / "case"
            )
            case = AppealCase(bundle)
            screening = case.screen_appeal(
                appeal_cid=appeal_cid,
                decision=decision,
                screened_by=screened_by,
                reasons=reasons,
                screened_at=screened_at,
            )
            artifacts = [screening]
            identity_seed = load_or_create_seed(self.keys_dir / IDENTITY_SEED_FILE)
            screening_cid = artifact_cid(screening)
            artifacts.append(
                make_signature_signed(
                    seed=identity_seed, domain=DOMAIN_APPEAL_SCREENING,
                    payload=screening_cid, signed_at=screened_at,
                )
            )
            self._persist(case_ref, artifacts, screened_at)
            return {
                "caseRef": case_ref,
                "screeningRef": str(screening_cid),
                "appealRef": appeal_cid,
                "decision": decision,
                "screenedAt": screened_at,
            }

    # -- store persistence -------------------------------------------------------

    def _persist(
        self,
        case_ref: str,
        artifacts: list[dict],
        at: str,
    ) -> None:
        """Ingest bridge artifacts, grow the case log, re-track the row.

        Bridge filings mirror the M5 CLI's ``_sign_and_append`` semantics:
        artifacts + identity signature, transparency-log growth for the
        logged types, and no telemetry (appeals spend no model tokens).
        """

        from conclave_core.signing import LOG_ID, make_signed_tree_head_signed

        identity_seed = load_or_create_seed(self.keys_dir / IDENTITY_SEED_FILE)

        row = self.store.session(case_ref)
        if row is None:
            raise ValueError(f"no persisted case: {case_ref}")
        state = json.loads(row["state"])

        tracked = list(state.get("artifacts", []))
        new_leaves = []
        for artifact in artifacts:
            cid = self.store.ingest(artifact, at)
            cid_str = str(cid)
            if cid_str not in tracked:
                tracked.append(cid_str)
            if artifact.get("type") in LOGGED_TYPES:
                new_leaves.append(cid)

        # log growth for every new logged leaf; STH artifacts are tracked too
        sth_cids = list(state.get("sthCids", []))
        for leaf in new_leaves:
            tree_size, root = self.store.append_log_leaf(leaf, at, case_ref=case_ref)
            sth, sth_signature = make_signed_tree_head_signed(
                log_id=LOG_ID, tree_size=tree_size, root_hash=root,
                seed=identity_seed, published_at=at,
            )
            sth_cid = self.store.ingest(sth, at)
            self.store.ingest(sth_signature, at)
            for cid in (sth_cid, artifact_cid(sth_signature)):
                cid_str = str(cid)
                if cid_str not in tracked:
                    tracked.append(cid_str)
            sth_cids.append(str(sth_cid))

        state["artifacts"] = tracked
        state["sthCids"] = sth_cids
        self.store.upsert_session(
            case_ref,
            row["position"],
            json.dumps(state, sort_keys=True),
            int(row["tokens_used"]),
            utc_now(),
        )
