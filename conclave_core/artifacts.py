"""Conclave artifact model: typed, content-addressed deliberation DAG nodes.

Every artifact is a plain dict (str keys) that canonically serializes via
:mod:`conclave_core.cbor` and is addressed by a CIDv1 with the dag-cbor
multicodec (:func:`artifact_cid`). Verbatim byte blobs (persona input
snapshots, model outputs) are hashed separately as raw-codec CIDs.

Artifact DAG (v0.2.0 core, codecVersion 1):

- ``DeliberationManifest`` — root. References the question, evidence ledger,
  panel, protocol parameters, appended round CIDs, and (once issued) the
  verdict CID. New manifest versions are append-only: they carry the extra
  round CIDs and a ``supersedes`` link to the prior manifest version.
- ``Question``, ``EvidenceLedger``, ``PanelManifest``, ``ProtocolParams`` —
  immutable inputs pinned by the manifest. An ``EvidenceLedger`` may supersede
  an earlier ledger (T1 evidence route), preserving the original ledger CID.
- ``PersonaManifest`` — one per seat, version-addressed; the ``PanelManifest``
  records which persona versions were convened.
- ``Round`` — chain node: ``prev`` link, ``status`` (committed/aborted),
  ``turns`` links, ``distilledSummary`` link, optional ``supersedes`` link to
  the aborted round it retries. Aborted rounds stay in the DAG with a failure
  reason; they never disappear.
- ``Turn`` — one seat's contribution: exact input-context hash (raw CID of the
  exact prompt bytes the seat saw), model id, sampling parameters in integer
  micro-units, output CID, ledger citations, token/cost telemetry. Struck turns
  remain in the DAG with Marshall's objection linked — nothing is deleted.
- ``Summary`` — structured distillation of a round's raw turns.
- ``Verdict``, ``Dissent`` — decision record and first-class dissent.

Design rules, enforced by :func:`validate_artifact`:

- every artifact carries ``type`` and ``codecVersion``; a future change to the
  canonical encoder bumps ``codecVersion`` rather than silently changing
  output bytes;
- floats are banned — costs/temperature/etc. use integer micro-units;
- artifact-typed links use DAG-CBOR codec CIDs; verbatim blobs use RAW codec
  CIDs;
- cycles are broken structurally: rounds never link their manifest (the
  manifest links them), and turns carry ``roundIndex`` rather than a round
  link.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .cbor import encode
from .cid import Cid, MULTICODEC_DAG_CBOR, MULTICODEC_RAW
from .mldsa import ALGORITHM, PK_SIZE, SIG_SIZE, public_fingerprint

CODEC_VERSION = 1

TYPE_DELIBERATION_MANIFEST = "DeliberationManifest"
TYPE_QUESTION = "Question"
TYPE_EVIDENCE_LEDGER = "EvidenceLedger"
TYPE_PERSONA_MANIFEST = "PersonaManifest"
TYPE_PANEL_MANIFEST = "PanelManifest"
TYPE_PROTOCOL_PARAMS = "ProtocolParams"
TYPE_ROUND = "Round"
TYPE_TURN = "Turn"
TYPE_SUMMARY = "Summary"
TYPE_VERDICT = "Verdict"
TYPE_DISSENT = "Dissent"
TYPE_SIGNATURE = "Signature"
TYPE_KEY_PUBLICATION = "KeyPublication"
TYPE_CERTIFICATE = "Certificate"
TYPE_SIGNED_TREE_HEAD = "SignedTreeHead"
TYPE_TELEMETRY = "Telemetry"

ARTIFACT_TYPES = (
    TYPE_DELIBERATION_MANIFEST,
    TYPE_QUESTION,
    TYPE_EVIDENCE_LEDGER,
    TYPE_PERSONA_MANIFEST,
    TYPE_PANEL_MANIFEST,
    TYPE_PROTOCOL_PARAMS,
    TYPE_ROUND,
    TYPE_TURN,
    TYPE_SUMMARY,
    TYPE_VERDICT,
    TYPE_DISSENT,
    TYPE_SIGNATURE,
    TYPE_KEY_PUBLICATION,
    TYPE_CERTIFICATE,
    TYPE_SIGNED_TREE_HEAD,
    TYPE_TELEMETRY,
)

KEY_ROLES = ("identity", "orchestrator", "persona-registry")

MODELS = ("sonnet", "opus", "local", "haiku-class")


class ArtifactError(ValueError):
    """Raised when an artifact is not structurally valid."""


def utc_now() -> str:
    """ISO-8601 UTC timestamp string (``...Z``), the artifact time format."""

    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# small validators
# ---------------------------------------------------------------------------


def _req(d: dict, name: str, context: str):
    if name not in d:
        raise ArtifactError(f"{context}: missing required field '{name}'")
    return d[name]


def _expect_str(value, context: str, field: str):
    if not isinstance(value, str):
        raise ArtifactError(f"{context}.{field}: expected str, got {type(value).__name__}")
    if value == "":
        raise ArtifactError(f"{context}.{field}: must not be empty")
    return value


def _expect_str_opt(value, context: str, field: str):
    if value is None:
        return None
    return _expect_str(value, context, field)


def _expect_str_items(value, context: str, field: str):
    for index, element in enumerate(value):
        _expect_str(element, f"{context}.{field}[{index}]", "text")


def _expect_bytes(value, context: str, field: str, length: int | None = None):
    if not isinstance(value, (bytes, bytearray)):
        raise ArtifactError(f"{context}.{field}: expected bytes, got {type(value).__name__}")
    if length is not None and len(value) != length:
        raise ArtifactError(f"{context}.{field}: expected {length} bytes, got {len(value)}")
    return bytes(value)


def _expect_int(value, context: str, field: str, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArtifactError(
            f"{context}.{field}: expected int, got {type(value).__name__} (floats are banned)"
        )
    if minimum is not None and value < minimum:
        raise ArtifactError(f"{context}.{field}: {value} below minimum {minimum}")
    if maximum is not None and value > maximum:
        raise ArtifactError(f"{context}.{field}: {value} above maximum {maximum}")
    return value


def _expect_int_opt(value, context: str, field: str, minimum=None, maximum=None):
    if value is None:
        return None
    return _expect_int(value, context, field, minimum, maximum)


def _expect_bool(value, context: str, field: str):
    if not isinstance(value, bool):
        raise ArtifactError(f"{context}.{field}: expected bool, got {type(value).__name__}")
    return value


def _expect_cid(value, context: str, field: str, codec: int = MULTICODEC_DAG_CBOR):
    if not isinstance(value, Cid):
        raise ArtifactError(f"{context}.{field}: expected a Cid link, got {type(value).__name__}")
    if value.codec != codec:
        codec_name = "dag-cbor" if codec == MULTICODEC_DAG_CBOR else "raw"
        raise ArtifactError(f"{context}.{field}: expected a {codec_name}-codec CID")
    return value


def _expect_cid_opt(value, context: str, field: str, codec: int = MULTICODEC_DAG_CBOR):
    if value is None:
        return None
    return _expect_cid(value, context, field, codec)


def _expect_cid_list(value, context: str, field: str, codec: int = MULTICODEC_DAG_CBOR):
    if not isinstance(value, list):
        raise ArtifactError(f"{context}.{field}: expected list of Cid links, got {type(value).__name__}")
    for index, element in enumerate(value):
        _expect_cid(element, f"{context}.{field}[{index}]", "cid", codec)
    return value


def _expect_list(value, context: str, field: str, item=None):
    if not isinstance(value, list):
        raise ArtifactError(f"{context}.{field}: expected list, got {type(value).__name__}")
    if item is str:
        _expect_str_items(value, context, field)
    elif item is dict:
        for index, element in enumerate(value):
            if not isinstance(element, dict):
                raise ArtifactError(f"{context}.{field}[{index}]: expected dict, got {type(element).__name__}")
    return value


def _expect_enum(value, context: str, field: str, allowed: tuple):
    if not isinstance(value, str) or value not in allowed:
        raise ArtifactError(f"{context}.{field}: expected one of {sorted(allowed)}, got {value!r}")
    return value


def _check_unknown(d: dict, allowed: tuple, context: str) -> None:
    unknown = sorted(set(d.keys()) - set(allowed) - {"type", "codecVersion"})
    if unknown:
        raise ArtifactError(f"{context}: unknown fields {unknown}")


def _base(d: dict, expected_type: str) -> dict:
    if not isinstance(d, dict):
        raise ArtifactError(f"artifact must be a dict, got {type(d).__name__}")
    artifact_type = d.get("type")
    if artifact_type != expected_type:
        raise ArtifactError(f"expected type {expected_type!r}, got {artifact_type!r}")
    version = d.get("codecVersion")
    if isinstance(version, bool) or version != CODEC_VERSION:
        raise ArtifactError(f"{expected_type}: unsupported codecVersion {version!r}")
    return d


# ---------------------------------------------------------------------------
# per-type validation
# ---------------------------------------------------------------------------


def validate_question(obj: dict) -> None:
    d = _base(obj, TYPE_QUESTION)
    _expect_str(_req(d, "text", TYPE_QUESTION), TYPE_QUESTION, "text")
    _expect_str(_req(d, "askedBy", TYPE_QUESTION), TYPE_QUESTION, "askedBy")
    _expect_str(_req(d, "askedAt", TYPE_QUESTION), TYPE_QUESTION, "askedAt")
    options = d.get("options")
    if options is not None:
        seen: set[str] = set()
        for index, option in enumerate(options):
            context = f"{TYPE_QUESTION}.options[{index}]"
            if not isinstance(option, dict):
                raise ArtifactError(f"{context}: expected dict")
            option_id = _expect_str(_req(option, "id", context), context, "id")
            if option_id in seen:
                raise ArtifactError(f"{context}: duplicate option id {option_id!r}")
            seen.add(option_id)
            _expect_str(_req(option, "label", context), context, "label")
            unknown = set(option.keys()) - {"id", "label"}
            if unknown:
                raise ArtifactError(f"{context}: unknown fields {sorted(unknown)}")
    if d.get("note") is not None:
        _expect_str(d["note"], TYPE_QUESTION, "note")
    _check_unknown(d, ("text", "askedBy", "askedAt", "options", "note"), TYPE_QUESTION)


def validate_evidence_ledger(obj: dict) -> None:
    d = _base(obj, TYPE_EVIDENCE_LEDGER)
    entries = _req(d, "entries", TYPE_EVIDENCE_LEDGER)
    _expect_list(entries, TYPE_EVIDENCE_LEDGER, "entries", dict)
    _expect_str(_req(d, "createdAt", TYPE_EVIDENCE_LEDGER), TYPE_EVIDENCE_LEDGER, "createdAt")
    _expect_cid_opt(d.get("supersedes"), TYPE_EVIDENCE_LEDGER, "supersedes")
    seen_ids: set[str] = set()
    expected_index = 1
    for index, entry in enumerate(entries):
        context = f"{TYPE_EVIDENCE_LEDGER}.entries[{index}]"
        entry_id = _expect_str(_req(entry, "id", context), context, "id")
        if entry_id != f"E{expected_index}":
            raise ArtifactError(
                f"{context}: ledger IDs must be contiguous E1,E2,...; found {entry_id!r}"
            )
        expected_index += 1
        if entry_id in seen_ids:
            raise ArtifactError(f"{context}: duplicate ledger id {entry_id}")
        seen_ids.add(entry_id)
        _expect_str(_req(entry, "item", context), context, "item")
        provenance = _req(entry, "provenance", context)
        if not isinstance(provenance, dict):
            raise ArtifactError(f"{context}.provenance: expected dict")
        _expect_str(_req(provenance, "source", f"{context}.provenance"), f"{context}.provenance", "source")
        _expect_str(_req(provenance, "kind", f"{context}.provenance"), f"{context}.provenance", "kind")
        if "handling" not in entry:
            raise ArtifactError(f"{context}: missing required field 'handling'")
        _expect_str(entry["handling"], context, "handling")
        if "sensitivity" in entry:
            _expect_str(entry["sensitivity"], context, "sensitivity")
        if "addedAtRound" in entry:
            _expect_int(entry["addedAtRound"], context, "addedAtRound", minimum=0)
        _check_unknown(entry, ("id", "item", "provenance", "handling", "sensitivity", "addedAtRound"), context)
    _check_unknown(d, ("entries", "createdAt", "supersedes"), TYPE_EVIDENCE_LEDGER)


def validate_persona_manifest(obj: dict) -> None:
    d = _base(obj, TYPE_PERSONA_MANIFEST)
    for name in ("seatId", "displayName", "tier", "lens", "stance", "version"):
        _expect_str(_req(d, name, TYPE_PERSONA_MANIFEST), TYPE_PERSONA_MANIFEST, name)
    moves = _req(d, "howYouArgue", TYPE_PERSONA_MANIFEST)
    _expect_list(moves, TYPE_PERSONA_MANIFEST, "howYouArgue", str)
    _expect_str(_req(d, "characteristicBias", TYPE_PERSONA_MANIFEST), TYPE_PERSONA_MANIFEST, "characteristicBias")
    is_not = _req(d, "isNot", TYPE_PERSONA_MANIFEST)
    _expect_list(is_not, TYPE_PERSONA_MANIFEST, "isNot", str)
    _expect_str_opt(d.get("polarityPartner"), TYPE_PERSONA_MANIFEST, "polarityPartner")
    _expect_enum(_req(d, "model", TYPE_PERSONA_MANIFEST), TYPE_PERSONA_MANIFEST, "model", MODELS)
    _expect_cid_opt(d.get("sourceDigest"), TYPE_PERSONA_MANIFEST, "sourceDigest", MULTICODEC_RAW)
    if d.get("note") is not None:
        _expect_str(d["note"], TYPE_PERSONA_MANIFEST, "note")
    _check_unknown(
        d,
        (
            "seatId", "displayName", "tier", "lens", "stance", "howYouArgue",
            "characteristicBias", "isNot", "polarityPartner", "model", "version",
            "sourceDigest", "note",
        ),
        TYPE_PERSONA_MANIFEST,
    )


def validate_panel_manifest(obj: dict) -> None:
    d = _base(obj, TYPE_PANEL_MANIFEST)
    seats = _req(d, "seats", TYPE_PANEL_MANIFEST)
    _expect_list(seats, TYPE_PANEL_MANIFEST, "seats", dict)
    _expect_str(_req(d, "convenedAt", TYPE_PANEL_MANIFEST), TYPE_PANEL_MANIFEST, "convenedAt")
    seen: set[str] = set()
    has_marshall = False
    for index, seat in enumerate(seats):
        context = f"{TYPE_PANEL_MANIFEST}.seats[{index}]"
        seat_id = _expect_str(_req(seat, "seatId", context), context, "seatId")
        if seat_id in seen:
            raise ArtifactError(f"{context}: seat {seat_id!r} convened twice")
        seen.add(seat_id)
        if seat_id == "conclave-marshall":
            has_marshall = True
        _expect_cid(seat.get("persona"), context, "persona")
        _expect_enum(_req(seat, "model", context), context, "model", MODELS)
        _check_unknown(seat, ("seatId", "persona", "model"), context)
    if not has_marshall:
        raise ArtifactError(f"{TYPE_PANEL_MANIFEST}: Marshall (conclave-marshall) must be convened")
    if d.get("quorum") is not None:
        _expect_int(d["quorum"], TYPE_PANEL_MANIFEST, "quorum", minimum=2, maximum=33)
    _check_unknown(d, ("seats", "convenedAt", "quorum"), TYPE_PANEL_MANIFEST)


def validate_protocol_params(obj: dict) -> None:
    d = _base(obj, TYPE_PROTOCOL_PARAMS)
    for name in (
        "quorum", "maxRounds", "wordBudgetRound1", "wordBudgetRound2",
        "wordBudgetCrossExamination", "summaryTokenBudget", "appealDefaultWindowDays",
    ):
        _expect_int(_req(d, name, TYPE_PROTOCOL_PARAMS), TYPE_PROTOCOL_PARAMS, name, minimum=1, maximum=1_000_000)
    _expect_int(
        d.get("earlyExitThresholdPct", 100), TYPE_PROTOCOL_PARAMS, "earlyExitThresholdPct",
        minimum=1, maximum=100,
    )
    _expect_str(_req(d, "recordedBy", TYPE_PROTOCOL_PARAMS), TYPE_PROTOCOL_PARAMS, "recordedBy")
    _check_unknown(
        d,
        (
            "quorum", "maxRounds", "wordBudgetRound1", "wordBudgetRound2",
            "wordBudgetCrossExamination", "summaryTokenBudget", "earlyExitThresholdPct",
            "appealDefaultWindowDays", "recordedBy",
        ),
        TYPE_PROTOCOL_PARAMS,
    )


def validate_summary(obj: dict) -> None:
    d = _base(obj, TYPE_SUMMARY)
    _expect_int(_req(d, "roundIndex", TYPE_SUMMARY), TYPE_SUMMARY, "roundIndex", minimum=0)
    distilled = _req(d, "distilledFrom", TYPE_SUMMARY)
    _expect_cid_list(distilled, TYPE_SUMMARY, "distilledFrom")
    if not distilled:
        raise ArtifactError(f"{TYPE_SUMMARY}.distilledFrom: must distill at least one turn")
    positions = _req(d, "positions", TYPE_SUMMARY)
    _expect_list(positions, TYPE_SUMMARY, "positions", dict)
    for index, position in enumerate(positions):
        context = f"{TYPE_SUMMARY}.positions[{index}]"
        _expect_str(_req(position, "seatId", context), context, "seatId")
        _expect_str(_req(position, "stance", context), context, "stance")
        citations = position.get("citations", [])
        _expect_list(citations, context, "citations", str)
        _check_unknown(position, ("seatId", "stance", "citations"), context)
    _expect_str(_req(d, "summaryText", TYPE_SUMMARY), TYPE_SUMMARY, "summaryText")
    disagreements = d.get("openDisagreements", [])
    _expect_list(disagreements, TYPE_SUMMARY, "openDisagreements", str)
    if d.get("fidelityObjections") is not None:
        _expect_list(d["fidelityObjections"], TYPE_SUMMARY, "fidelityObjections", str)
    _expect_str(_req(d, "writtenAt", TYPE_SUMMARY), TYPE_SUMMARY, "writtenAt")
    _expect_str_opt(d.get("modelId"), TYPE_SUMMARY, "modelId")
    if d.get("wordCount") is not None:
        _expect_int(d["wordCount"], TYPE_SUMMARY, "wordCount", minimum=1)
    _check_unknown(
        d,
        (
            "roundIndex", "distilledFrom", "positions", "summaryText",
            "openDisagreements", "writtenAt", "modelId", "wordCount", "fidelityObjections",
        ),
        TYPE_SUMMARY,
    )


def validate_turn(obj: dict) -> None:
    d = _base(obj, TYPE_TURN)
    _expect_int(_req(d, "roundIndex", TYPE_TURN), TYPE_TURN, "roundIndex", minimum=0)
    _expect_str(_req(d, "seatId", TYPE_TURN), TYPE_TURN, "seatId")
    _expect_cid(_req(d, "persona", TYPE_TURN), TYPE_TURN, "persona")
    _expect_cid(_req(d, "inputContextHash", TYPE_TURN), TYPE_TURN, "inputContextHash", MULTICODEC_RAW)
    _expect_str(_req(d, "modelId", TYPE_TURN), TYPE_TURN, "modelId")
    sampling = _req(d, "sampling", TYPE_TURN)
    if not isinstance(sampling, dict):
        raise ArtifactError(f"{TYPE_TURN}.sampling: expected dict")
    for name in ("temperatureMicro", "topPMicro", "maxOutputTokens"):
        _expect_int(_req(sampling, name, f"{TYPE_TURN}.sampling"), f"{TYPE_TURN}.sampling", name, minimum=0)
    _check_unknown(sampling, ("temperatureMicro", "topPMicro", "maxOutputTokens"), f"{TYPE_TURN}.sampling")
    if d.get("seed") is not None:
        _expect_int(d["seed"], TYPE_TURN, "seed", 0, 2**31)
    _expect_cid(_req(d, "output", TYPE_TURN), TYPE_TURN, "output", MULTICODEC_RAW)
    _expect_list(_req(d, "citations", TYPE_TURN), TYPE_TURN, "citations", str)
    tokens = d.get("tokens")
    if tokens is not None:
        if not isinstance(tokens, dict):
            raise ArtifactError(f"{TYPE_TURN}.tokens: expected dict")
        for name, value in tokens.items():
            if name not in ("inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens"):
                raise ArtifactError(f"{TYPE_TURN}.tokens: unknown field {name!r}")
            _expect_int(value, f"{TYPE_TURN}.tokens", name, minimum=0)
    _expect_int_opt(d.get("costMicroUsd"), TYPE_TURN, "costMicroUsd", minimum=0)
    _expect_cid_opt(d.get("telemetry"), TYPE_TURN, "telemetry")
    struck = _expect_bool(d.get("struck", False), TYPE_TURN, "struck")
    if struck:
        _expect_str(_req(d, "struckReason", TYPE_TURN), TYPE_TURN, "struckReason")
        _expect_cid(_req(d, "marshallObjection", TYPE_TURN), TYPE_TURN, "marshallObjection")
    elif "struckReason" in d or "marshallObjection" in d:
        raise ArtifactError(f"{TYPE_TURN}: struckReason/marshallObjection require struck=true")
    _expect_str(_req(d, "recordedAt", TYPE_TURN), TYPE_TURN, "recordedAt")
    if d.get("providerRun") is not None:
        _expect_bool(d["providerRun"], TYPE_TURN, "providerRun")
    if d.get("note") is not None:
        _expect_str(d["note"], TYPE_TURN, "note")
    _check_unknown(
        d,
        (
            "roundIndex", "seatId", "persona", "inputContextHash", "modelId",
            "sampling", "seed", "output", "citations", "recordedAt", "tokens",
            "costMicroUsd", "telemetry", "struck", "struckReason",
            "marshallObjection", "providerRun", "note",
        ),
        TYPE_TURN,
    )


def validate_round(obj: dict) -> None:
    d = _base(obj, TYPE_ROUND)
    _expect_int(_req(d, "index", TYPE_ROUND), TYPE_ROUND, "index", minimum=0)
    _expect_cid_opt(_req(d, "prev", TYPE_ROUND), TYPE_ROUND, "prev")
    _expect_enum(_req(d, "status", TYPE_ROUND), TYPE_ROUND, "status", ("committed", "aborted"))
    status = d["status"]
    _expect_cid_opt(d.get("supersedes"), TYPE_ROUND, "supersedes")
    if status == "aborted":
        _expect_str(_req(d, "failureReason", TYPE_ROUND), TYPE_ROUND, "failureReason")
    else:
        turns = d.get("turns")
        if turns is not None:
            _expect_cid_list(turns, TYPE_ROUND, "turns")
        distilled = d.get("distilledSummary")
        _expect_cid_opt(distilled, TYPE_ROUND, "distilledSummary")
        if turns and distilled is None and "noDistillationReason" not in d:
            raise ArtifactError(
                f"{TYPE_ROUND}: committed round carries turns but neither a distilledSummary "
                "nor an explicit noDistillationReason"
            )
        if "noDistillationReason" in d:
            _expect_str(d["noDistillationReason"], TYPE_ROUND, "noDistillationReason")
    _expect_list(_req(d, "participants", TYPE_ROUND), TYPE_ROUND, "participants", str)
    _expect_str(_req(d, "openedAt", TYPE_ROUND), TYPE_ROUND, "openedAt")
    if d.get("closedAt") is not None:
        _expect_str(d["closedAt"], TYPE_ROUND, "closedAt")
    if d.get("roundKind") is not None:
        _expect_str(d["roundKind"], TYPE_ROUND, "roundKind")
    _check_unknown(
        d,
        (
            "index", "prev", "status", "participants", "openedAt", "turns",
            "distilledSummary", "supersedes", "failureReason", "roundKind",
            "noDistillationReason", "closedAt",
        ),
        TYPE_ROUND,
    )


def validate_dissent(obj: dict) -> None:
    d = _base(obj, TYPE_DISSENT)
    _expect_cid(_req(d, "round", TYPE_DISSENT), TYPE_DISSENT, "round")
    _expect_str(_req(d, "seatId", TYPE_DISSENT), TYPE_DISSENT, "seatId")
    _expect_cid(_req(d, "persona", TYPE_DISSENT), TYPE_DISSENT, "persona")
    _expect_str(_req(d, "grounds", TYPE_DISSENT), TYPE_DISSENT, "grounds")
    _expect_list(_req(d, "citedLedgerIds", TYPE_DISSENT), TYPE_DISSENT, "citedLedgerIds", str)
    if d.get("citedTurns") is not None:
        _expect_cid_list(d["citedTurns"], TYPE_DISSENT, "citedTurns")
    _expect_cid_opt(d.get("signature"), TYPE_DISSENT, "signature", MULTICODEC_RAW)
    _expect_str(_req(d, "filedAt", TYPE_DISSENT), TYPE_DISSENT, "filedAt")
    _check_unknown(
        d,
        ("round", "seatId", "persona", "grounds", "citedLedgerIds", "citedTurns", "signature", "filedAt"),
        TYPE_DISSENT,
    )


def validate_verdict(obj: dict) -> None:
    d = _base(obj, TYPE_VERDICT)
    _expect_cid(_req(d, "manifest", TYPE_VERDICT), TYPE_VERDICT, "manifest")
    _expect_cid(_req(d, "finalRound", TYPE_VERDICT), TYPE_VERDICT, "finalRound")
    _expect_str(_req(d, "decision", TYPE_VERDICT), TYPE_VERDICT, "decision")
    recommendation = _req(d, "recommendation", TYPE_VERDICT)
    _expect_str(recommendation, TYPE_VERDICT, "recommendation")
    if not recommendation.startswith("The Sovereign Conclave advises"):
        raise ArtifactError(
            f"{TYPE_VERDICT}.recommendation: must begin 'The Sovereign Conclave advises' (D-4)"
        )
    votes = _req(d, "votes", TYPE_VERDICT)
    _expect_list(votes, TYPE_VERDICT, "votes", dict)
    for index, vote in enumerate(votes):
        context = f"{TYPE_VERDICT}.votes[{index}]"
        _expect_str(_req(vote, "seatId", context), context, "seatId")
        _expect_cid(_req(vote, "persona", context), context, "persona")
        _expect_str(_req(vote, "stance", context), context, "stance")
        _expect_int(_req(vote, "weightMicro", context), context, "weightMicro", minimum=0)
        _check_unknown(vote, ("seatId", "persona", "stance", "weightMicro"), context)
    if d.get("dissents") is not None:
        _expect_cid_list(d["dissents"], TYPE_VERDICT, "dissents")
    _expect_enum(_req(d, "confidence", TYPE_VERDICT), TYPE_VERDICT, "confidence", ("low", "medium", "high"))
    _expect_cid_opt(d.get("marshallVerification"), TYPE_VERDICT, "marshallVerification")
    _expect_cid_opt(d.get("signature"), TYPE_VERDICT, "signature", MULTICODEC_RAW)
    if d.get("optionsRanked") is not None:
        _expect_list(d["optionsRanked"], TYPE_VERDICT, "optionsRanked", str)
    if d.get("whatWouldChangeIt") is not None:
        _expect_str(d["whatWouldChangeIt"], TYPE_VERDICT, "whatWouldChangeIt")
    if d.get("dissentRecordedNote") is not None:
        _expect_str(d["dissentRecordedNote"], TYPE_VERDICT, "dissentRecordedNote")
    _expect_str(_req(d, "issuedAt", TYPE_VERDICT), TYPE_VERDICT, "issuedAt")
    _check_unknown(
        d,
        (
            "manifest", "finalRound", "decision", "recommendation", "votes",
            "confidence", "issuedAt", "dissents", "marshallVerification",
            "signature", "optionsRanked", "whatWouldChangeIt", "dissentRecordedNote",
        ),
        TYPE_VERDICT,
    )


def validate_manifest(obj: dict) -> None:
    d = _base(obj, TYPE_DELIBERATION_MANIFEST)
    _expect_str(_req(d, "caseId", TYPE_DELIBERATION_MANIFEST), TYPE_DELIBERATION_MANIFEST, "caseId")
    _expect_cid(_req(d, "question", TYPE_DELIBERATION_MANIFEST), TYPE_DELIBERATION_MANIFEST, "question")
    _expect_cid(_req(d, "evidenceLedger", TYPE_DELIBERATION_MANIFEST), TYPE_DELIBERATION_MANIFEST, "evidenceLedger")
    _expect_cid(_req(d, "panel", TYPE_DELIBERATION_MANIFEST), TYPE_DELIBERATION_MANIFEST, "panel")
    _expect_cid(_req(d, "protocolParams", TYPE_DELIBERATION_MANIFEST), TYPE_DELIBERATION_MANIFEST, "protocolParams")
    _expect_cid_list(_req(d, "rounds", TYPE_DELIBERATION_MANIFEST), TYPE_DELIBERATION_MANIFEST, "rounds")
    _expect_cid_opt(_req(d, "verdict", TYPE_DELIBERATION_MANIFEST), TYPE_DELIBERATION_MANIFEST, "verdict")
    _expect_cid_opt(d.get("supersedes"), TYPE_DELIBERATION_MANIFEST, "supersedes")
    if d["verdict"] is not None and d.get("supersedes") is None:
        # A verdict links the manifest version it was issued against; the
        # issuing manifest cannot contain the verdict (that would require the
        # two CIDs to depend on each other). The final manifest therefore
        # supersedes the pre-verdict version and carries the verdict link.
        raise ArtifactError(
            f"{TYPE_DELIBERATION_MANIFEST}: verdict-bearing manifest must supersede the "
            "pre-verdict manifest version"
        )
    _expect_str(_req(d, "openedAt", TYPE_DELIBERATION_MANIFEST), TYPE_DELIBERATION_MANIFEST, "openedAt")
    if d.get("title") is not None:
        _expect_str(d["title"], TYPE_DELIBERATION_MANIFEST, "title")
    if d.get("note") is not None:
        _expect_str(d["note"], TYPE_DELIBERATION_MANIFEST, "note")
    _check_unknown(
        d,
        (
            "caseId", "question", "evidenceLedger", "panel", "protocolParams",
            "rounds", "verdict", "supersedes", "openedAt", "title", "note",
        ),
        TYPE_DELIBERATION_MANIFEST,
    )


def validate_key_publication(obj: dict) -> None:
    d = _base(obj, TYPE_KEY_PUBLICATION)
    _expect_enum(d.get("algorithm"), TYPE_KEY_PUBLICATION, "algorithm", (ALGORITHM,))
    _expect_enum(_req(d, "role", TYPE_KEY_PUBLICATION), TYPE_KEY_PUBLICATION, "role", KEY_ROLES)
    _expect_str(_req(d, "keyFingerprint", TYPE_KEY_PUBLICATION), TYPE_KEY_PUBLICATION, "keyFingerprint")
    public_key = _expect_bytes(
        _req(d, "publicKey", TYPE_KEY_PUBLICATION), TYPE_KEY_PUBLICATION, "publicKey", PK_SIZE
    )
    computed = public_fingerprint(public_key)
    if d["keyFingerprint"] != computed:
        raise ArtifactError(
            f"{TYPE_KEY_PUBLICATION}: keyFingerprint {d['keyFingerprint'][:16]}… does not match "
            f"the published public key ({computed[:16]}…)"
        )
    _expect_str(_req(d, "publishedAt", TYPE_KEY_PUBLICATION), TYPE_KEY_PUBLICATION, "publishedAt")
    if d.get("note") is not None:
        _expect_str(d["note"], TYPE_KEY_PUBLICATION, "note")
    _check_unknown(
        d, ("algorithm", "role", "keyFingerprint", "publicKey", "publishedAt", "note"),
        TYPE_KEY_PUBLICATION,
    )


def validate_certificate(obj: dict) -> None:
    d = _base(obj, TYPE_CERTIFICATE)
    _expect_cid(_req(d, "subjectKey", TYPE_CERTIFICATE), TYPE_CERTIFICATE, "subjectKey")
    _expect_cid(_req(d, "caseManifest", TYPE_CERTIFICATE), TYPE_CERTIFICATE, "caseManifest")
    _expect_str(_req(d, "issuedAt", TYPE_CERTIFICATE), TYPE_CERTIFICATE, "issuedAt")
    if d.get("note") is not None:
        _expect_str(d["note"], TYPE_CERTIFICATE, "note")
    _check_unknown(d, ("subjectKey", "caseManifest", "issuedAt", "note"), TYPE_CERTIFICATE)


def validate_signature(obj: dict) -> None:
    d = _base(obj, TYPE_SIGNATURE)
    _expect_enum(d.get("algorithm"), TYPE_SIGNATURE, "algorithm", (ALGORITHM,))
    domain = _expect_str(_req(d, "domain", TYPE_SIGNATURE), TYPE_SIGNATURE, "domain")
    if len(domain) > 200:
        raise ArtifactError(f"{TYPE_SIGNATURE}.domain: domain string too long")
    _expect_str(_req(d, "keyFingerprint", TYPE_SIGNATURE), TYPE_SIGNATURE, "keyFingerprint")
    _expect_cid(_req(d, "payload", TYPE_SIGNATURE), TYPE_SIGNATURE, "payload")
    _expect_str(_req(d, "signedAt", TYPE_SIGNATURE), TYPE_SIGNATURE, "signedAt")
    _expect_bytes(_req(d, "signature", TYPE_SIGNATURE), TYPE_SIGNATURE, "signature", SIG_SIZE)
    if d.get("note") is not None:
        _expect_str(d["note"], TYPE_SIGNATURE, "note")
    _check_unknown(
        d, ("algorithm", "domain", "keyFingerprint", "payload", "signedAt", "signature", "note"),
        TYPE_SIGNATURE,
    )


def validate_signed_tree_head(obj: dict) -> None:
    d = _base(obj, TYPE_SIGNED_TREE_HEAD)
    _expect_str(_req(d, "logId", TYPE_SIGNED_TREE_HEAD), TYPE_SIGNED_TREE_HEAD, "logId")
    _expect_int(_req(d, "treeSize", TYPE_SIGNED_TREE_HEAD), TYPE_SIGNED_TREE_HEAD, "treeSize", minimum=0)
    _expect_bytes(_req(d, "rootHash", TYPE_SIGNED_TREE_HEAD), TYPE_SIGNED_TREE_HEAD, "rootHash", 32)
    _expect_str(_req(d, "publishedAt", TYPE_SIGNED_TREE_HEAD), TYPE_SIGNED_TREE_HEAD, "publishedAt")
    if d.get("note") is not None:
        _expect_str(d["note"], TYPE_SIGNED_TREE_HEAD, "note")
    _check_unknown(d, ("logId", "treeSize", "rootHash", "publishedAt", "note"), TYPE_SIGNED_TREE_HEAD)


def validate_telemetry(obj: dict) -> None:
    d = _base(obj, TYPE_TELEMETRY)
    _expect_cid(_req(d, "subject", TYPE_TELEMETRY), TYPE_TELEMETRY, "subject")
    _expect_enum(_req(d, "subjectKind", TYPE_TELEMETRY), TYPE_TELEMETRY, "subjectKind",
                 ("turn", "summary", "round"))
    tokens = _req(d, "tokens", TYPE_TELEMETRY)
    if not isinstance(tokens, dict):
        raise ArtifactError(f"{TYPE_TELEMETRY}.tokens: expected dict")
    if "inputTokens" not in tokens or "outputTokens" not in tokens:
        raise ArtifactError(f"{TYPE_TELEMETRY}.tokens: inputTokens and outputTokens are required")
    for name, value in tokens.items():
        if name not in ("inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens"):
            raise ArtifactError(f"{TYPE_TELEMETRY}.tokens: unknown field {name!r}")
        _expect_int(value, f"{TYPE_TELEMETRY}.tokens", name, minimum=0)
    _expect_str(_req(d, "modelId", TYPE_TELEMETRY), TYPE_TELEMETRY, "modelId")
    _expect_str(_req(d, "provider", TYPE_TELEMETRY), TYPE_TELEMETRY, "provider")
    _expect_int(_req(d, "latencyMs", TYPE_TELEMETRY), TYPE_TELEMETRY, "latencyMs", minimum=0)
    if d.get("inputParts") is not None:
        input_parts = d["inputParts"]
        if not isinstance(input_parts, dict):
            raise ArtifactError(f"{TYPE_TELEMETRY}.inputParts: expected dict")
        for name, value in input_parts.items():
            if name not in ("staticChars", "dynamicChars", "suffixChars"):
                raise ArtifactError(f"{TYPE_TELEMETRY}.inputParts: unknown field {name!r}")
            _expect_int(value, f"{TYPE_TELEMETRY}.inputParts", name, minimum=0)
    _expect_bool(_req(d, "estimated", TYPE_TELEMETRY), TYPE_TELEMETRY, "estimated")
    _expect_bool(_req(d, "batch", TYPE_TELEMETRY), TYPE_TELEMETRY, "batch")
    _expect_int_opt(d.get("costMicroUsd"), TYPE_TELEMETRY, "costMicroUsd", minimum=0)
    _expect_str(_req(d, "recordedAt", TYPE_TELEMETRY), TYPE_TELEMETRY, "recordedAt")
    if d.get("note") is not None:
        _expect_str(d["note"], TYPE_TELEMETRY, "note")
    _check_unknown(
        d,
        (
            "subject", "subjectKind", "tokens", "modelId", "provider",
            "latencyMs", "inputParts", "estimated", "batch", "costMicroUsd",
            "recordedAt", "note",
        ),
        TYPE_TELEMETRY,
    )


_VALIDATORS = {
    TYPE_QUESTION: validate_question,
    TYPE_EVIDENCE_LEDGER: validate_evidence_ledger,
    TYPE_PERSONA_MANIFEST: validate_persona_manifest,
    TYPE_PANEL_MANIFEST: validate_panel_manifest,
    TYPE_PROTOCOL_PARAMS: validate_protocol_params,
    TYPE_ROUND: validate_round,
    TYPE_TURN: validate_turn,
    TYPE_SUMMARY: validate_summary,
    TYPE_VERDICT: validate_verdict,
    TYPE_DISSENT: validate_dissent,
    TYPE_DELIBERATION_MANIFEST: validate_manifest,
    TYPE_KEY_PUBLICATION: validate_key_publication,
    TYPE_CERTIFICATE: validate_certificate,
    TYPE_SIGNATURE: validate_signature,
    TYPE_SIGNED_TREE_HEAD: validate_signed_tree_head,
    TYPE_TELEMETRY: validate_telemetry,
}


def validate_artifact(obj) -> None:
    """Validate any conclave artifact dict; raises ArtifactError on failure."""

    if not isinstance(obj, dict):
        raise ArtifactError(f"artifact must be a dict, got {type(obj).__name__}")
    validator = _VALIDATORS.get(obj.get("type"))
    if validator is None:
        raise ArtifactError(f"unknown artifact type {obj.get('type')!r}")
    validator(obj)


def artifact_bytes(obj: dict) -> bytes:
    """Canonical DAG-CBOR bytes for an artifact (validates first)."""

    validate_artifact(obj)
    return encode(obj)


def artifact_cid(obj: dict) -> Cid:
    """Content address of an artifact: CIDv1 over canonical DAG-CBOR bytes."""

    return Cid.of_bytes(MULTICODEC_DAG_CBOR, artifact_bytes(obj))


def raw_cid(payload: bytes) -> Cid:
    """Content address of verbatim bytes (raw codec), e.g. prompt or output."""

    return Cid.of_bytes(MULTICODEC_RAW, payload)


def link(obj: dict) -> Cid:
    """Inline-content-address an artifact and return its link."""

    return artifact_cid(obj)


# ---------------------------------------------------------------------------
# DAG-level verification (cid → artifact resolution with hash recomputation)
# ---------------------------------------------------------------------------


def verify_manifest(manifest: dict, resolver) -> list[str]:
    """Verify a manifest and everything reachable below it.

    ``resolver`` maps a Cid to the artifact it addresses (or None when the
    referenced artifact is unknown). Each resolution re-canonicalizes the
    resolved artifact and checks its CID, so verification recomputes every
    hash. Returns a list of problems; empty means the manifest and its DAG
    are fully verified.
    """

    problems: list[str] = []

    def resolve_checked(cid: Cid, label: str):
        artifact = resolver(cid)
        if artifact is None:
            problems.append(f"{label}: artifact {cid} not found")
            return None
        if not isinstance(artifact, dict):
            problems.append(f"{label}: artifact {cid} is not a dict")
            return None
        try:
            recomputed = artifact_cid(artifact)
        except ArtifactError as exc:
            problems.append(f"{label}: artifact {cid} invalid: {exc}")
            return None
        if recomputed != cid:
            problems.append(f"{label}: CID mismatch (stored {cid}, content hashes to {recomputed})")
            return None
        return artifact

    try:
        artifact_cid(manifest)  # validates manifest intactness + schema
    except ArtifactError as exc:
        problems.append(f"manifest: invalid: {exc}")
        return problems

    if manifest.get("supersedes"):
        prior = resolve_checked(manifest["supersedes"], "manifest.supersedes")
        if prior is not None and prior.get("type") == TYPE_DELIBERATION_MANIFEST:
            try:
                validate_artifact(prior)
            except ArtifactError as exc:
                problems.append(f"manifest.supersedes: prior manifest invalid: {exc}")
            else:
                prior_round_ids = prior["rounds"]
                current_round_ids = manifest["rounds"]
                if len(current_round_ids) < len(prior_round_ids) or current_round_ids[: len(prior_round_ids)] != prior_round_ids:
                    problems.append(
                        "manifest.supersedes: superseding manifest must preserve the prior "
                        "manifest's rounds as a prefix (append-only)"
                    )
                if manifest["verdict"] is not None and prior.get("verdict") is not None:
                    problems.append(
                        "manifest.supersedes: the pre-verdict manifest must not already "
                        "carry a verdict"
                    )

    question = resolve_checked(manifest["question"], "manifest.question")
    ledger = resolve_checked(manifest["evidenceLedger"], "manifest.evidenceLedger")
    panel = resolve_checked(manifest["panel"], "manifest.panel")
    params = resolve_checked(manifest["protocolParams"], "manifest.protocolParams")
    for artifact, label in (
        (question, "question"), (ledger, "evidenceLedger"),
        (panel, "panel"), (params, "protocolParams"),
    ):
        if artifact is not None and artifact.get("type") != {
            "question": TYPE_QUESTION, "evidenceLedger": TYPE_EVIDENCE_LEDGER,
            "panel": TYPE_PANEL_MANIFEST, "protocolParams": TYPE_PROTOCOL_PARAMS,
        }[label]:
            problems.append(f"manifest.{label}: resolved artifact has type {artifact.get('type')!r}")

    previous = None
    for pointer, round_cid in enumerate(manifest["rounds"]):
        round_artifact = resolve_checked(round_cid, f"manifest.rounds[{pointer}]")
        if round_artifact is None or round_artifact.get("type") != TYPE_ROUND:
            if round_artifact is not None:
                problems.append(f"manifest.rounds[{pointer}]: expected a Round artifact")
            previous = round_cid
            continue
        if round_artifact["index"] != pointer:
            problems.append(
                f"manifest.rounds[{pointer}]: round index {round_artifact['index']} != position {pointer}"
            )
        if previous is None and round_artifact["prev"] is not None:
            problems.append(f"manifest.rounds[{pointer}]: first round must have prev=null")
        if previous is not None and round_artifact["prev"] != previous:
            problems.append(
                f"manifest.rounds[{pointer}]: prev {round_artifact['prev']} does not match the "
                f"previous round link {previous}"
            )
        previous = round_cid
        if round_artifact.get("supersedes"):
            superseded = resolve_checked(round_artifact["supersedes"], f"round[{pointer}].supersedes")
            if superseded is not None:
                if superseded.get("type") != TYPE_ROUND:
                    problems.append(f"round[{pointer}].supersedes: target is not a Round")
                elif superseded.get("status") != "aborted":
                    problems.append(
                        f"round[{pointer}].supersedes: only aborted rounds may be superseded"
                    )
                else:
                    for turn_cid in superseded.get("turns", []) or []:
                        resolve_checked(turn_cid, f"round[{pointer}].supersedes[].turns")
        for turn_pointer, turn_cid in enumerate(round_artifact.get("turns", [])):
            turn = resolve_checked(turn_cid, f"round[{pointer}].turns[{turn_pointer}]")
            if turn is not None:
                if turn.get("type") != TYPE_TURN:
                    problems.append(f"round[{pointer}].turns[{turn_pointer}]: expected a Turn artifact")
                else:
                    if turn["roundIndex"] != pointer:
                        problems.append(
                            f"round[{pointer}].turns[{turn_pointer}]: roundIndex "
                            f"{turn['roundIndex']} != round position {pointer}"
                        )
        summary_cid = round_artifact.get("distilledSummary")
        if summary_cid is not None:
            summary = resolve_checked(summary_cid, f"round[{pointer}].distilledSummary")
            if summary is not None and summary.get("type") != TYPE_SUMMARY:
                problems.append(f"round[{pointer}].distilledSummary: expected a Summary artifact")

    if manifest["verdict"] is not None:
        verdict = resolve_checked(manifest["verdict"], "manifest.verdict")
        if verdict is not None and verdict.get("type") == TYPE_VERDICT:
            expected_manifest = manifest.get("supersedes")
            if verdict["manifest"] != expected_manifest:
                problems.append(
                    f"manifest.verdict: verdict issued against manifest {verdict['manifest']}, "
                    f"not the pre-verdict manifest version {expected_manifest}"
                )
            if not manifest["rounds"]:
                problems.append("manifest.verdict: verdict issued before any round completed")
            elif verdict["finalRound"] != manifest["rounds"][-1]:
                problems.append(
                    f"manifest.verdict: finalRound {verdict['finalRound']} is not the last round "
                    f"{manifest['rounds'][-1]}"
                )
            for pointer, dissent_cid in enumerate(verdict.get("dissents", [])):
                dissent = resolve_checked(dissent_cid, f"verdict.dissents[{pointer}]")
                if dissent is not None and dissent.get("type") != TYPE_DISSENT:
                    problems.append(f"verdict.dissents[{pointer}]: expected a Dissent artifact")

    return problems


# ---------------------------------------------------------------------------
# builders (constructing pre-validated, canonical-ready artifacts)
# ---------------------------------------------------------------------------


def make_question(text: str, *, options=None, asked_by: str, asked_at: str | None = None, note: str | None = None) -> dict:
    question = {
        "type": TYPE_QUESTION,
        "codecVersion": CODEC_VERSION,
        "text": text,
        "askedBy": asked_by,
        "askedAt": asked_at or utc_now(),
    }
    if options is not None:
        question["options"] = options
    if note is not None:
        question["note"] = note
    validate_artifact(question)
    return question


def make_evidence_ledger(entries, *, supersedes: Cid | None = None, created_at: str | None = None) -> dict:
    ledger = {
        "type": TYPE_EVIDENCE_LEDGER,
        "codecVersion": CODEC_VERSION,
        "entries": list(entries),
        "createdAt": created_at or utc_now(),
    }
    if supersedes is not None:
        ledger["supersedes"] = supersedes
    validate_artifact(ledger)
    return ledger


def make_persona(
    seat_id: str, display_name: str, tier: str, lens: str, stance: str,
    how_you_argue, characteristic_bias: str, is_not, model: str, version: str,
    *, polarity_partner: str | None = None, source_digest: Cid | None = None,
) -> dict:
    persona = {
        "type": TYPE_PERSONA_MANIFEST,
        "codecVersion": CODEC_VERSION,
        "seatId": seat_id,
        "displayName": display_name,
        "tier": tier,
        "lens": lens,
        "stance": stance,
        "howYouArgue": list(how_you_argue),
        "characteristicBias": characteristic_bias,
        "isNot": list(is_not),
        "model": model,
        "version": version,
    }
    if polarity_partner is not None:
        persona["polarityPartner"] = polarity_partner
    if source_digest is not None:
        persona["sourceDigest"] = source_digest
    validate_artifact(persona)
    return persona


def make_panel(seats, *, quorum: int | None = None, convened_at: str | None = None) -> dict:
    panel = {
        "type": TYPE_PANEL_MANIFEST,
        "codecVersion": CODEC_VERSION,
        "seats": seats,
        "convenedAt": convened_at or utc_now(),
    }
    if quorum is not None:
        panel["quorum"] = quorum
    validate_artifact(panel)
    return panel


def make_protocol_params(
    *, quorum: int = 6, max_rounds: int = 4, word_budget_round1: int = 400,
    word_budget_round2: int = 300, word_budget_cross_examination: int = 300,
    summary_token_budget: int = 1200, early_exit_threshold_pct: int = 85,
    appeal_default_window_days: int = 30, recorded_by: str,
) -> dict:
    params = {
        "type": TYPE_PROTOCOL_PARAMS,
        "codecVersion": CODEC_VERSION,
        "quorum": quorum,
        "maxRounds": max_rounds,
        "wordBudgetRound1": word_budget_round1,
        "wordBudgetRound2": word_budget_round2,
        "wordBudgetCrossExamination": word_budget_cross_examination,
        "summaryTokenBudget": summary_token_budget,
        "earlyExitThresholdPct": early_exit_threshold_pct,
        "appealDefaultWindowDays": appeal_default_window_days,
        "recordedBy": recorded_by,
    }
    validate_artifact(params)
    return params


def make_turn(
    *, round_index: int, seat_id: str, persona: Cid, input_context_hash: Cid,
    model_id: str, output: Cid, citations, temperature_micro: int = 1000000,
    top_p_micro: int = 1000000, max_output_tokens: int = 4096, seed: int | None = None,
    tokens: dict | None = None, cost_micro_usd: int | None = None,
    telemetry: Cid | None = None,
    struck: bool = False, struck_reason: str | None = None,
    marshall_objection: Cid | None = None, recorded_at: str | None = None,
    provider_run: bool | None = None, note: str | None = None,
) -> dict:
    turn = {
        "type": TYPE_TURN,
        "codecVersion": CODEC_VERSION,
        "roundIndex": round_index,
        "seatId": seat_id,
        "persona": persona,
        "inputContextHash": input_context_hash,
        "modelId": model_id,
        "sampling": {
            "temperatureMicro": temperature_micro,
            "topPMicro": top_p_micro,
            "maxOutputTokens": max_output_tokens,
        },
        "seed": seed,
        "output": output,
        "citations": list(citations),
        "recordedAt": recorded_at or utc_now(),
    }
    if tokens is not None:
        turn["tokens"] = tokens
    if cost_micro_usd is not None:
        turn["costMicroUsd"] = cost_micro_usd
    if telemetry is not None:
        turn["telemetry"] = telemetry
    if provider_run is not None:
        turn["providerRun"] = provider_run
    if note is not None:
        turn["note"] = note
    if struck:
        turn["struck"] = True
        turn["struckReason"] = struck_reason
        turn["marshallObjection"] = marshall_objection
    validate_artifact(turn)
    return turn


def make_summary(
    *, round_index: int, distilled_from, positions, summary_text: str,
    open_disagreements=None, written_at: str | None = None,
    model_id: str | None = None, word_count: int | None = None,
) -> dict:
    summary = {
        "type": TYPE_SUMMARY,
        "codecVersion": CODEC_VERSION,
        "roundIndex": round_index,
        "distilledFrom": list(distilled_from),
        "positions": positions,
        "summaryText": summary_text,
        "writtenAt": written_at or utc_now(),
    }
    if open_disagreements is not None:
        summary["openDisagreements"] = list(open_disagreements)
    if model_id is not None:
        summary["modelId"] = model_id
    if word_count is not None:
        summary["wordCount"] = word_count
    validate_artifact(summary)
    return summary


def make_round(
    *, index: int, prev: Cid | None, status: str = "committed", participants,
    opened_at: str | None = None, closed_at: str | None = None,
    turns=None, distilled_summary: Cid | None = None, supersedes: Cid | None = None,
    failure_reason: str | None = None, round_kind: str | None = None,
    no_distillation_reason: str | None = None,
) -> dict:
    round_artifact = {
        "type": TYPE_ROUND,
        "codecVersion": CODEC_VERSION,
        "index": index,
        "prev": prev,
        "status": status,
        "participants": list(participants),
        "openedAt": opened_at or utc_now(),
    }
    if supersedes is not None:
        round_artifact["supersedes"] = supersedes
    if status == "aborted":
        round_artifact["failureReason"] = failure_reason
    else:
        if turns:
            round_artifact["turns"] = list(turns)
        if no_distillation_reason is not None:
            round_artifact["noDistillationReason"] = no_distillation_reason
        elif distilled_summary is not None:
            round_artifact["distilledSummary"] = distilled_summary
    if closed_at is not None:
        round_artifact["closedAt"] = closed_at
    if round_kind is not None:
        round_artifact["roundKind"] = round_kind
    validate_artifact(round_artifact)
    return round_artifact


def make_dissent(
    *, round_cid: Cid, seat_id: str, persona: Cid, grounds: str,
    cited_ledger_ids, cited_turns=None, signature: Cid | None = None,
    filed_at: str | None = None,
) -> dict:
    dissent = {
        "type": TYPE_DISSENT,
        "codecVersion": CODEC_VERSION,
        "round": round_cid,
        "seatId": seat_id,
        "persona": persona,
        "grounds": grounds,
        "citedLedgerIds": list(cited_ledger_ids),
        "filedAt": filed_at or utc_now(),
    }
    if cited_turns is not None:
        dissent["citedTurns"] = list(cited_turns)
    if signature is not None:
        dissent["signature"] = signature
    validate_artifact(dissent)
    return dissent


def make_verdict(
    *, manifest: Cid, final_round: Cid, decision: str, recommendation: str,
    votes, confidence: str, dissents=None, marshall_verification: Cid | None = None,
    signature: Cid | None = None, options_ranked=None, what_would_change_it: str | None = None,
    dissent_recorded_note: str | None = None, issued_at: str | None = None,
) -> dict:
    verdict = {
        "type": TYPE_VERDICT,
        "codecVersion": CODEC_VERSION,
        "manifest": manifest,
        "finalRound": final_round,
        "decision": decision,
        "recommendation": recommendation,
        "votes": votes,
        "confidence": confidence,
        "issuedAt": issued_at or utc_now(),
    }
    if dissents is not None:
        verdict["dissents"] = list(dissents)
    if marshall_verification is not None:
        verdict["marshallVerification"] = marshall_verification
    if signature is not None:
        verdict["signature"] = signature
    if options_ranked is not None:
        verdict["optionsRanked"] = list(options_ranked)
    if what_would_change_it is not None:
        verdict["whatWouldChangeIt"] = what_would_change_it
    if dissent_recorded_note is not None:
        verdict["dissentRecordedNote"] = dissent_recorded_note
    validate_artifact(verdict)
    return verdict


def make_manifest(
    *, case_id: str, question: Cid, evidence_ledger: Cid, panel: Cid,
    protocol_params: Cid, rounds=None, verdict: Cid | None = None,
    supersedes: Cid | None = None, title: str | None = None, note: str | None = None,
    opened_at: str | None = None,
) -> dict:
    manifest = {
        "type": TYPE_DELIBERATION_MANIFEST,
        "codecVersion": CODEC_VERSION,
        "caseId": case_id,
        "question": question,
        "evidenceLedger": evidence_ledger,
        "panel": panel,
        "protocolParams": protocol_params,
        "rounds": list(rounds or []),
        "verdict": verdict,
        "openedAt": opened_at or utc_now(),
    }
    if supersedes is not None:
        manifest["supersedes"] = supersedes
    if title is not None:
        manifest["title"] = title
    if note is not None:
        manifest["note"] = note
    validate_artifact(manifest)
    return manifest


def make_key_publication(*, role: str, public_key: bytes, published_at: str | None = None, note: str | None = None) -> dict:
    key_publication = {
        "type": TYPE_KEY_PUBLICATION,
        "codecVersion": CODEC_VERSION,
        "algorithm": ALGORITHM,
        "role": role,
        "keyFingerprint": public_fingerprint(public_key),
        "publicKey": bytes(public_key),
        "publishedAt": published_at or utc_now(),
    }
    if note is not None:
        key_publication["note"] = note
    validate_artifact(key_publication)
    return key_publication


def make_certificate(*, subject_key: Cid, case_manifest: Cid, issued_at: str | None = None, note: str | None = None) -> dict:
    certificate = {
        "type": TYPE_CERTIFICATE,
        "codecVersion": CODEC_VERSION,
        "subjectKey": subject_key,
        "caseManifest": case_manifest,
        "issuedAt": issued_at or utc_now(),
    }
    if note is not None:
        certificate["note"] = note
    validate_artifact(certificate)
    return certificate


def make_signature(*, domain: str, key_fingerprint: str, payload: Cid, signature: bytes, signed_at: str | None = None, note: str | None = None) -> dict:
    signature_artifact = {
        "type": TYPE_SIGNATURE,
        "codecVersion": CODEC_VERSION,
        "algorithm": ALGORITHM,
        "domain": domain,
        "keyFingerprint": key_fingerprint,
        "payload": payload,
        "signedAt": signed_at or utc_now(),
        "signature": bytes(signature),
    }
    if note is not None:
        signature_artifact["note"] = note
    validate_artifact(signature_artifact)
    return signature_artifact


def make_signed_tree_head(*, log_id: str, tree_size: int, root_hash: bytes, published_at: str | None = None, note: str | None = None) -> dict:
    signed_tree_head = {
        "type": TYPE_SIGNED_TREE_HEAD,
        "codecVersion": CODEC_VERSION,
        "logId": log_id,
        "treeSize": tree_size,
        "rootHash": bytes(root_hash),
        "publishedAt": published_at or utc_now(),
    }
    if note is not None:
        signed_tree_head["note"] = note
    validate_artifact(signed_tree_head)
    return signed_tree_head


def make_telemetry(
    *, subject: Cid, subject_kind: str, tokens: dict, model_id: str, provider: str,
    latency_ms: int, estimated: bool = False, batch: bool = False,
    input_parts: dict | None = None,
    cost_micro_usd: int | None = None, recorded_at: str | None = None,
    note: str | None = None,
) -> dict:
    telemetry = {
        "type": TYPE_TELEMETRY,
        "codecVersion": CODEC_VERSION,
        "subject": subject,
        "subjectKind": subject_kind,
        "tokens": dict(tokens),
        "modelId": model_id,
        "provider": provider,
        "latencyMs": latency_ms,
        "estimated": estimated,
        "batch": batch,
        "recordedAt": recorded_at or utc_now(),
    }
    if input_parts is not None:
        telemetry["inputParts"] = dict(input_parts)
    if cost_micro_usd is not None:
        telemetry["costMicroUsd"] = cost_micro_usd
    if note is not None:
        telemetry["note"] = note
    validate_artifact(telemetry)
    return telemetry
