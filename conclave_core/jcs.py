"""Non-normative JCS-JSON view of conclave artifacts (RFC 8785 subset).

The DAG-CBOR encoding in :mod:`conclave_core.cbor` is the **normative**
canonical form of every conclave artifact and the input to every CID hash.
This module emits the standardized human/hand-tool-friendly JSON twin of the
same value: RFC 8785 (JSON Canonicalization Scheme) over the *no-floats*
subset the conclave uses (integers only).

Scope notes, so nobody mistakes this quad for normative:

- The output is labeled NON-NORMATIVE everywhere it is written; a CIDs must
  always be computed from ``conclave_core.cbor.encode``, never from JSON.
- Artifact map keys are ASCII, so UTF-8 bytewise ordering (DAG-CBOR) matches
  JCS's UTF-16 code-unit ordering for artifacts; string values may be any
  Unicode.
- Integers serialize in minimal decimal form, which is exact for the 64-bit
  range DAG-CBOR permits; the JCS float machinery never engages.

Dependency-free (stdlib only).
"""

from __future__ import annotations

import json

_ESCAPES = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
}


class JcsError(ValueError):
    """Raised when a value cannot be emitted as canonical JSON."""


def _encode_str(value: str) -> str:
    out = ['"']
    for ch in value:
        code = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif code < 0x20:
            short = _ESCAPES.get(code)
            if short is not None:
                out.append(short)
            else:
                out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def jcs_string(value, out: list[str]) -> None:
    """Append the RFC 8785 canonical JSON text of ``value`` to ``out``."""

    if value is None:
        out.append("null")
        return
    if value is True:
        out.append("true")
        return
    if value is False:
        out.append("false")
        return
    if isinstance(value, float):
        raise JcsError("floats are banned in conclave artifacts (use integer micro-units)")
    if isinstance(value, int):
        out.append(str(value))
        return
    if isinstance(value, str):
        out.append(_encode_str(value))
        return
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise JcsError("byte strings have no canonical JSON form (hex/base64 is viewer-defined)")
    if isinstance(value, list):
        out.append("[")
        for index, item in enumerate(value):
            if index:
                out.append(",")
            jcs_string(item, out)
        out.append("]")
        return
    if isinstance(value, dict):
        out.append("{")
        # RFC 8785 sorts object members by UTF-16 code units, i.e. by their
        # UTF-16BE bytes; equivalent to bytewise order for the ASCII artifact
        # keys the conclave schema mandates.
        first = True
        for key in sorted(value.keys(), key=lambda k: k.encode("utf-16-be")):
            if first:
                first = False
            else:
                out.append(",")
            jcs_string(key, out)
            out.append(":")
            jcs_string(value[key], out)
        out.append("}")
        return
    raise JcsError(f"cannot emit JSON canonical form of type {type(value).__name__}")


def jcs(value) -> str:
    """Canonical JSON text (RFC 8785 subset: no floats) for a conclave value."""

    out: list[str] = []
    jcs_string(value, out)
    return "".join(out)


def jcs_bytes(value) -> bytes:
    """UTF-8 canonical JSON bytes (non-normative view)."""

    return jcs(value).encode("utf-8")


def round_trips_via_json(data: bytes) -> bool:
    """True when strict JSON round-trips against the canonical bytes view."""

    try:
        parsed = json.loads(data.decode("utf-8"))
        return json.loads(jcs(parsed)) == parsed
    except (ValueError, UnicodeDecodeError):
        return False
