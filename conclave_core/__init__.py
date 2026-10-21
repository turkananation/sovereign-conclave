"""Sovereign Conclave canonical core (v0.2.0).

Pure-Python, dependency-free primitives for verifiable deliberation
artifacts:

- :mod:`conclave_core.cbor` — canonical DAG-CBOR serialization (normative;
  the input to every CID hash). Floats are banned; costs use integer
  micro-units.
- :mod:`conclave_core.cid` — CIDv1 content identifiers (dag-cbor/raw codecs,
  sha2-256, base32 'b' multibase strings).
- :mod:`conclave_core.jcs` — NON-NORMATIVE JCS-JSON view of the same values.
- :mod:`conclave_core.artifacts` — typed artifact model, validators, DAG
  verifier, and builders for the deliberation artifact DAG.

This package is importable by the deliberation skill (via the ``bin/conclave``
CLI) and by future verification services; it deliberately has no
provider/network dependencies.
"""

from .artifacts import (
    ArtifactError,
    CODEC_VERSION,
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
    ARTIFACT_TYPES,
    artifact_bytes,
    artifact_cid,
    link,
    raw_cid,
    validate_artifact,
    verify_manifest,
    make_question,
    make_evidence_ledger,
    make_persona,
    make_panel,
    make_protocol_params,
    make_turn,
    make_summary,
    make_round,
    make_dissent,
    make_verdict,
    make_manifest,
    utc_now,
)
from .cbor import DagCborError, decode, encode, is_canonical
from .cid import Cid, CidError, parse

__all__ = [
    "ArtifactError",
    "CODEC_VERSION",
    "ARTIFACT_TYPES",
    "TYPE_DELIBERATION_MANIFEST",
    "TYPE_QUESTION",
    "TYPE_EVIDENCE_LEDGER",
    "TYPE_PERSONA_MANIFEST",
    "TYPE_PANEL_MANIFEST",
    "TYPE_PROTOCOL_PARAMS",
    "TYPE_ROUND",
    "TYPE_TURN",
    "TYPE_SUMMARY",
    "TYPE_VERDICT",
    "TYPE_DISSENT",
    "Cid",
    "CidError",
    "DagCborError",
    "artifact_bytes",
    "artifact_cid",
    "link",
    "raw_cid",
    "validate_artifact",
    "verify_manifest",
    "encode",
    "decode",
    "is_canonical",
    "parse",
    "make_question",
    "make_evidence_ledger",
    "make_persona",
    "make_panel",
    "make_protocol_params",
    "make_turn",
    "make_summary",
    "make_round",
    "make_dissent",
    "make_verdict",
    "make_manifest",
    "utc_now",
]
