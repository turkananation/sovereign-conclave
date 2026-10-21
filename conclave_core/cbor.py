"""Deterministic DAG-CBOR encoding and strict decoding.

Implements the IPLD DAG-CBOR etymology of RFC 8949 CBOR as Sovereign Conclave's
canonical artifact serialization, restricted to the conclave's value surface:

- definite-length encodings only (no indefinite arrays/maps/strings);
- map keys must be strings, sorted strictly increasing by their UTF-8 bytes;
- integers must fit the RFC 8949 64-bit range and use minimal-length encodings;
- **floats are banned** (the conclave represents costs in integer micro-units);
- no tags other than 42 (CID links);
- a strict decoder rejects non-canonical encodings so re-encoding a decoded
  value always reproduces the original bytes.

CIDs (conclave_core.cid.Cid) encode as CBOR tag 42 with the identity-multibase
prefix 0x00 followed by the CID bytes, exactly as specified by the DAG-CBOR
link encoding.

The encoder is intentionally dependency-free (stdlib only) so deliberation
artifacts can be produced and verified offline.
"""

from __future__ import annotations

from .cid import Cid

_MAJOR_UNSIGNED = 0
_MAJOR_NEGATIVE = 1
_MAJOR_BYTES = 2
_MAJOR_TEXT = 3
_MAJOR_ARRAY = 4
_MAJOR_MAP = 5
_MAJOR_TAG = 6
_MAJOR_SIMPLE = 7

_TAG_CID = 42

_UINT_MAX = 2**64 - 1
_NEG_MIN = -(2**64)

_SIMPLE_FALSE = 20
_SIMPLE_TRUE = 21
_SIMPLE_NULL = 22


class DagCborError(ValueError):
    """Raised when a value cannot be canonically encoded or decoded."""


def _encode_head(major: int, value: int) -> bytes:
    if value < 24:
        return bytes([(major << 5) | value])
    if value < 0x100:
        return bytes([(major << 5) | 24, value])
    if value < 0x10000:
        return bytes([(major << 5) | 25]) + value.to_bytes(2, "big")
    if value < 0x1_0000_0000:
        return bytes([(major << 5) | 26]) + value.to_bytes(4, "big")
    if value <= _UINT_MAX:
        return bytes([(major << 5) | 27]) + value.to_bytes(8, "big")
    raise DagCborError(f"integer magnitude {value} exceeds the DAG-CBOR 64-bit limit")


def encode(value) -> bytes:
    """Encode a Python value to canonical DAG-CBOR bytes."""

    out = bytearray()
    _encode_into(value, out)
    return bytes(out)


def _encode_into(value, out: bytearray) -> None:
    # bool must be tested before int (bool is an int subclass).
    if value is None:
        out.append(0xF6)
        return
    if value is True:
        out.append(0xF5)
        return
    if value is False:
        out.append(0xF4)
        return
    if isinstance(value, int):
        if value > _UINT_MAX or value < _NEG_MIN:
            raise DagCborError(f"integer {value} outside the DAG-CBOR integer range")
        if value >= 0:
            out += _encode_head(_MAJOR_UNSIGNED, value)
        else:
            out += _encode_head(_MAJOR_NEGATIVE, -1 - value)
        return
    if isinstance(value, float):
        raise DagCborError("floats are banned in conclave artifacts (use integer micro-units)")
    if isinstance(value, str):
        data = value.encode("utf-8")
        out += _encode_head(_MAJOR_TEXT, len(data))
        out += data
        return
    if isinstance(value, (bytes, bytearray, memoryview)):
        data = bytes(value)
        out += _encode_head(_MAJOR_BYTES, len(data))
        out += data
        return
    if isinstance(value, Cid):
        # DAG-CBOR link form: tag 42 wrapping 0x00 (identity multibase) + CID.
        body = b"\x00" + value.cid_bytes()
        out += _encode_head(_MAJOR_TAG, _TAG_CID)
        out += _encode_head(_MAJOR_BYTES, len(body))
        out += body
        return
    if isinstance(value, (list, tuple)):
        out += _encode_head(_MAJOR_ARRAY, len(value))
        for item in value:
            _encode_into(item, out)
        return
    if isinstance(value, dict):
        keys = list(value.keys())
        for key in keys:
            if not isinstance(key, str):
                raise DagCborError(f"map keys must be strings (got {type(key).__name__})")
        out += _encode_head(_MAJOR_MAP, len(keys))
        for key in sorted(keys, key=lambda k: k.encode("utf-8")):
            _encode_into(key, out)
            _encode_into(value[key], out)
        return
    raise DagCborError(f"cannot encode value of type {type(value).__name__}")


def decode(data: bytes):
    """Strictly decode canonical DAG-CBOR bytes; rejects non-canonical forms."""

    value, consumed = _decode_at(bytes(data), 0)
    if consumed != len(data):
        raise DagCborError(f"trailing bytes after CBOR value at offset {consumed}")
    return value


def _decode_head(data: bytes, offset: int):
    if offset >= len(data):
        raise DagCborError("truncated CBOR value")
    head = data[offset]
    major = head >> 5
    info = head & 0x1F
    offset += 1
    if info < 24:
        return major, info, offset
    if info == 24:
        if offset >= len(data):
            raise DagCborError("truncated CBOR value")
        value = data[offset]
        _check_minimal(major, value, info)
        return major, value, offset + 1
    if info == 25:
        if offset + 2 > len(data):
            raise DagCborError("truncated CBOR value")
        raw = int.from_bytes(data[offset : offset + 2], "big")
        _check_minimal(major, raw, info)
        return major, raw, offset + 2
    if info == 26:
        if offset + 4 > len(data):
            raise DagCborError("truncated CBOR value")
        raw = int.from_bytes(data[offset : offset + 4], "big")
        _check_minimal(major, raw, info)
        return major, raw, offset + 4
    if info == 27:
        if offset + 8 > len(data):
            raise DagCborError("truncated CBOR value")
        raw = int.from_bytes(data[offset : offset + 8], "big")
        _check_minimal(major, raw, info)
        return major, raw, offset + 8
    if info in (28, 29, 30):
        raise DagCborError(f"reserved CBOR additional info {info}")
    if info == 31:
        raise DagCborError("indefinite-length items are not canonical DAG-CBOR")
    raise DagCborError(f"invalid CBOR additional info {info}")


def _check_minimal(major: int, raw: int, info: int) -> None:
    """Reject non-minimal integer head encodings (strict canonical form)."""

    if info == 24 and raw < 24:
        raise DagCborError("non-minimal integer encoding")
    if info == 25 and raw < 0x100:
        raise DagCborError("non-minimal integer encoding")
    if info == 26 and raw < 0x1_0000:
        raise DagCborError("non-minimal integer encoding")
    if info == 27 and raw < 0x1_0000_0000:
        raise DagCborError("non-minimal integer encoding")


def _decode_at(data: bytes, offset: int):
    major, raw, offset = _decode_head(data, offset)
    if major == _MAJOR_UNSIGNED:
        if raw > _UINT_MAX:
            raise DagCborError("integer exceeds DAG-CBOR 64-bit range")
        return raw, offset
    if major == _MAJOR_NEGATIVE:
        value = -1 - raw
        if value < _NEG_MIN:
            raise DagCborError("integer exceeds DAG-CBOR 64-bit range")
        return value, offset
    if major == _MAJOR_BYTES:
        end = offset + raw
        if end > len(data):
            raise DagCborError("truncated byte string")
        return data[offset:end], end
    if major == _MAJOR_TEXT:
        end = offset + raw
        if end > len(data):
            raise DagCborError("truncated text string")
        try:
            text = data[offset:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DagCborError(f"invalid UTF-8 in text string: {exc}") from exc
        return text, end
    if major == _MAJOR_ARRAY:
        items = []
        for _ in range(raw):
            item, offset = _decode_at(data, offset)
            items.append(item)
        return items, offset
    if major == _MAJOR_MAP:
        result: dict = {}
        previous: bytes | None = None
        for _ in range(raw):
            key, offset = _decode_at(data, offset)
            if not isinstance(key, str):
                raise DagCborError("map keys must be strings")
            key_bytes = key.encode("utf-8")
            if previous is not None and not previous < key_bytes:
                raise DagCborError("map keys are not canonically sorted")
            previous = key_bytes
            value, offset = _decode_at(data, offset)
            result[key] = value
        return result, offset
    if major == _MAJOR_TAG:
        if raw != _TAG_CID:
            raise DagCborError(f"tag {raw} is not permitted in DAG-CBOR")
        body, offset = _decode_at(data, offset)
        if not isinstance(body, bytes):
            raise DagCborError("CID tag content must be a byte string")
        return _decode_cid_body(body), offset
    if major == _MAJOR_SIMPLE:
        if raw == _SIMPLE_FALSE:
            return False, offset
        if raw == _SIMPLE_TRUE:
            return True, offset
        if raw == _SIMPLE_NULL:
            return None, offset
        raise DagCborError(
            f"simple value {raw} is not permitted in DAG-CBOR (floats and undefined are banned)"
        )
    raise DagCborError(f"unknown CBOR major type {major}")


def _decode_cid_body(body: bytes) -> Cid:
    if body.startswith(b"\x00"):
        body = body[1:]  # identity multibase prefix is ignored on read
    if len(body) < 2 or body[0] != 0x01:
        raise DagCborError("CID tag content is not a CIDv1")
    return Cid(body)


def is_canonical(data: bytes) -> bool:
    """True when ``data`` decodes strictly and re-encodes identically."""

    try:
        return encode(decode(data)) == bytes(data)
    except (DagCborError, ValueError):
        return False
