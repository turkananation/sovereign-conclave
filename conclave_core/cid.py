"""Content identifiers (CIDv1) for the conclave canonical core.

Implements the subset of IPLD CIDv1, multibase, multihash, and multicodec that
Sovereign Conclave uses:

- multicodec values: ``dag-cbor`` (0x71) for canonical artifact blocks and
  ``raw`` (0x55) for verbatim byte blobs (e.g. hash-then-sign payloads and
  input-context snapshots);
- multihash: ``sha2-256`` (0x12), 32-byte digests;
- serialisation: base32 (RFC 4648) lowercase without padding, prefixed with
  ``b`` (CIDv1 multibase).

CIDs are content addresses: two artifacts with identical canonical bytes have
identical CIDs, and any CID can be re-derived independently from its bytes.
This module is dependency-free (stdlib only) so it can run offline in the
deliberation skill.

Canonical spec surface (normative, frozen):

- CIDv1 header: byte 0x01, unsigned varint multicodec, unsigned varint
  multihash code, unsigned varint multihash length, digest bytes.
- varints: unsigned LEB128 (7 bits per byte, little-endian, high bit marks
  continuation).
- Only sha2-256 (code 0x12) is accepted in this codec generation so that
  verification recomputes one hash layer.
"""

from __future__ import annotations

import base64
import hashlib
import re

MULTICODEC_DAG_CBOR = 0x71
MULTICODEC_RAW = 0x55

_MULTICODECS = (MULTICODEC_DAG_CBOR, MULTICODEC_RAW)

_MULTIBASE_PREFIX = "b"
_BASE32_RE = re.compile(r"^b[0-9a-z]+$")

HASH_CODE_SHA2_256 = 0x12
HASH_LENGTH_SHA2_256 = 32
_HASHES = (HASH_CODE_SHA2_256,)


class CidError(ValueError):
    """Raised when CID bytes or strings violate the supported codec surface."""


def _write_varint(value: int) -> bytes:
    """Unsigned LEB128 varint, as used by multihash/CID headers."""

    if value < 0:
        raise CidError("varint values are unsigned")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if offset >= len(data):
            raise CidError("truncated varint")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
        if shift > 63:
            raise CidError("varint exceeds 64 bits")


class Cid:
    """An immutable CIDv1 content identifier (dag-cbor or raw, sha2-256)."""

    __slots__ = ("_bytes",)

    def __init__(self, cid_bytes: bytes):
        if not isinstance(cid_bytes, bytes):
            raise CidError("CID bytes required")
        self._parse(cid_bytes)
        self._bytes = bytes(cid_bytes)

    @classmethod
    def of_bytes(cls, codec: int, payload: bytes) -> "Cid":
        """Hash ``payload`` with sha2-256 and wrap it as a CIDv1 link."""

        if not isinstance(payload, bytes):
            raise CidError("payload must be bytes")
        if codec not in _MULTICODECS:
            raise CidError(f"unsupported multicodec {codec:#x}")
        digest = hashlib.sha256(payload).digest()
        return cls.of_digest(codec, digest)

    @classmethod
    def of_digest(cls, codec: int, digest: bytes) -> "Cid":
        if codec not in _MULTICODECS:
            raise CidError(f"unsupported multicodec {codec:#x}")
        if not isinstance(digest, bytes) or len(digest) != HASH_LENGTH_SHA2_256:
            raise CidError("sha2-256 digests are exactly 32 bytes")
        data = b"\x01"
        data += _write_varint(codec)
        data += _write_varint(HASH_CODE_SHA2_256)
        data += _write_varint(HASH_LENGTH_SHA2_256)
        data += digest
        return cls(data)

    @property
    def codec(self) -> int:
        codec, _ = _read_varint(self._bytes, 1)
        return codec

    @property
    def digest(self) -> bytes:
        """The sha2-256 digest bytes backing this CID."""

        _, offset = _read_varint(self._bytes, 1)
        _, offset = _read_varint(self._bytes, offset)
        _, offset = _read_varint(self._bytes, offset)
        return self._bytes[offset:]

    def cid_bytes(self) -> bytes:
        """Binary CIDv1 bytes (header + multihash); the content address."""

        return self._bytes

    def __str__(self) -> str:
        encoded = base64.b32encode(self._bytes).decode("ascii")
        return _MULTIBASE_PREFIX + encoded.lower().rstrip("=")

    def __repr__(self) -> str:
        return f"Cid({str(self)!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Cid):
            return NotImplemented
        return self._bytes == other._bytes

    def __hash__(self) -> int:
        return hash(self._bytes)

    def _parse(self, data: bytes) -> None:
        if len(data) < 2:
            raise CidError("CID too short")
        if data[0] != 0x01:
            raise CidError(f"only CIDv1 is supported (got version {data[0]:#x})")
        codec, offset = _read_varint(data, 1)
        if codec not in _MULTICODECS:
            raise CidError(f"unsupported multicodec {codec:#x}")
        hash_code, offset = _read_varint(data, offset)
        hash_length, offset = _read_varint(data, offset)
        if hash_code != HASH_CODE_SHA2_256:
            raise CidError(f"unsupported multihash {hash_code:#x}")
        if hash_length != HASH_LENGTH_SHA2_256:
            raise CidError(f"sha2-256 length must be {HASH_LENGTH_SHA2_256}")
        if len(data) - offset != hash_length:
            raise CidError("multihash length does not match digest")


def parse(cid_str: str) -> Cid:
    """Parse a base32 CIDv1 string (``b...``) into a Cid."""

    if not isinstance(cid_str, str) or not _BASE32_RE.match(cid_str):
        raise CidError("expected a base32 CIDv1 string prefixed with 'b'")
    body = cid_str[1:].upper()
    body += "=" * ((-len(body)) % 8)
    raw = base64.b32decode(body)
    return Cid(raw)
