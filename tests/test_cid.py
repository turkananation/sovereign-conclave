"""Tests for CIDv1 content identifiers (conclave_core.cid)."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conclave_core.cid import (
    Cid,
    CidError,
    MULTICODEC_DAG_CBOR,
    MULTICODEC_RAW,
    parse,
)


class TestKnownVectors(unittest.TestCase):
    def test_empty_raw_cidv1(self) -> None:
        # Cross-checked against the IPLD reference implementation (py-cid):
        # 0x01 | raw(0x55) | sha2-256(0x12) | 32 | sha256(b"")
        cid = Cid.of_bytes(MULTICODEC_RAW, b"")
        self.assertEqual(
            cid.cid_bytes().hex(),
            "01551220e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )
        self.assertEqual(
            str(cid), "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"
        )

    def test_sha256_hello_digest_bytewise(self) -> None:
        cid = Cid.of_bytes(MULTICODEC_RAW, b"hello")
        self.assertEqual(
            cid.digest.hex(),
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        )

    def test_dag_cbor_empty_block(self) -> None:
        # canonical DAG-CBOR of the empty map is 0xa0
        cid = Cid.of_bytes(MULTICODEC_DAG_CBOR, b"\xa0")
        self.assertEqual(cid.codec, MULTICODEC_DAG_CBOR)
        self.assertEqual(cid.cid_bytes().hex(), "0171" + "1220" + hashlib.sha256(b"\xa0").hexdigest())
        self.assertTrue(str(cid).startswith("bafyre"))


class TestStructure(unittest.TestCase):
    def test_header_fields(self) -> None:
        cid = Cid.of_bytes(MULTICODEC_RAW, b"x")
        raw = cid.cid_bytes()
        self.assertEqual(raw[0], 0x01)
        self.assertEqual(raw[1], MULTICODEC_RAW)
        self.assertEqual(raw[2], 0x12)
        self.assertEqual(raw[3], 32)
        self.assertEqual(len(raw), 4 + 32)
        self.assertEqual(cid.digest, hashlib.sha256(b"x").digest())
        self.assertEqual(cid.codec, MULTICODEC_RAW)

    def test_round_trip_string(self) -> None:
        for payload in (b"", b"hello", bytes(range(256))):
            cid = Cid.of_bytes(MULTICODEC_DAG_CBOR, payload)
            reparsed = parse(str(cid))
            self.assertEqual(reparsed, cid)
            self.assertEqual(reparsed.cid_bytes(), cid.cid_bytes())

    def test_base32_is_lower_without_padding(self) -> None:
        cid = Cid.of_bytes(MULTICODEC_RAW, b"")
        text = str(cid)
        self.assertTrue(text.startswith("b"))
        self.assertEqual(text, text.lower())
        self.assertNotIn("=", text)
        self.assertGreater(len(text), 10)

    def test_hash_equality(self) -> None:
        a = Cid.of_bytes(MULTICODEC_RAW, b"same")
        b = Cid.of_bytes(MULTICODEC_RAW, b"same")
        c = Cid.of_bytes(MULTICODEC_RAW, b"different")
        self.assertEqual(hash(a), hash(b))
        self.assertEqual(len({a, b, c}), 2)


class TestRejection(unittest.TestCase):
    def test_cidv0_rejected(self) -> None:
        with self.assertRaises(CidError):
            Cid(b"\x12\x20" + b"\x00" * 32)  # CIDv0 header

    def test_unsupported_multicodec_rejected(self) -> None:
        with self.assertRaises(CidError):
            Cid(b"\x01\x50" + b"\x00" * 34)  # dag-pb codec

    def test_unsupported_multihash_rejected(self) -> None:
        with self.assertRaises(CidError):
            Cid(b"\x01\x55\x13" + b"\x20" + b"\x00" * 32)  # sha2-512

    def test_wrong_digest_length_rejected(self) -> None:
        with self.assertRaises(CidError):
            Cid(b"\x01\x55\x12\x31" + b"\x00" * 49)

    def test_truncated_rejected(self) -> None:
        with self.assertRaises(CidError):
            Cid(b"\x01\x55\x12\x20" + b"\x00" * 31)

    def test_of_digest_requires_32_bytes(self) -> None:
        with self.assertRaises(CidError):
            Cid.of_digest(MULTICODEC_RAW, b"\x00" * 31)

    def test_of_bytes_rejects_unknown_codec(self) -> None:
        with self.assertRaises(CidError):
            Cid.of_bytes(0x70, b"")  # dag-pb

    def test_parse_rejects_bad_forms(self) -> None:
        for bad in ("", "b", "b!!!!", "afknotbase32xd", "b_invalid"):
            with self.subTest(bad=bad):
                with self.assertRaises(CidError):
                    parse(bad)


if __name__ == "__main__":
    unittest.main()
