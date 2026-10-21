"""Tests for the canonical DAG-CBOR codec (conclave_core.cbor)."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conclave_core.cbor import DagCborError, decode, encode, is_canonical
from conclave_core.cid import Cid, MULTICODEC_RAW


def hex_of(value) -> str:
    return encode(value).hex()


class TestCanonicalScalars(unittest.TestCase):
    def test_int_minimal_encodings(self) -> None:
        cases = {
            0: "00",
            1: "01",
            10: "0a",
            23: "17",
            24: "1818",
            100: "1864",
            255: "18ff",
            256: "190100",
            1000: "1903e8",
            65535: "19ffff",
            65536: "1a00010000",
            4294967295: "1affffffff",
            4294967296: "1b0000000100000000",
            2**64 - 1: "1b" + "ff" * 8,
            -1: "20",
            -10: "29",
            -24: "37",
            -25: "3818",
            -100: "3863",
            -256: "38ff",
            -257: "390100",
            -(2**64): "3b" + "ff" * 8,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(hex_of(value), expected)
                self.assertEqual(decode(bytes.fromhex(expected)), value)

    def test_int_out_of_range_rejected(self) -> None:
        for value in (2**64, 2**65, -(2**64) - 1):
            with self.subTest(value=value):
                with self.assertRaises(DagCborError):
                    encode(value)

    def test_bools_and_null(self) -> None:
        self.assertEqual(hex_of(True), "f5")
        self.assertEqual(hex_of(False), "f4")
        self.assertEqual(hex_of(None), "f6")
        self.assertIs(decode(bytes.fromhex("f5")), True)
        self.assertIs(decode(bytes.fromhex("f4")), False)
        self.assertIs(decode(bytes.fromhex("f6")), None)

    def test_bool_is_not_int(self) -> None:
        # True must encode as major 7 (bool), never as unsigned integer 1.
        self.assertEqual(hex_of(True), "f5")
        self.assertNotEqual(hex_of(True), hex_of(1))
        self.assertIs(decode(bytes.fromhex("f5")), True)

    def test_floats_are_banned(self) -> None:
        for value in (0.0, 1.5, 2.5e300):
            with self.subTest(value=value):
                with self.assertRaises(DagCborError):
                    encode(value)
        with self.assertRaises(DagCborError):
            encode({"a": [1, {"b": 2.5}]})

    def test_float_head_bytes_rejected_on_decode(self) -> None:
        # Half (0xf9), float32 (0xfa), float64 (0xfb) heads are banned.
        for head, filler in (("f9", "3f80"), ("fa", "3f800000"), ("fb", "3ff0000000000000")):
            with self.subTest(head=head):
                with self.assertRaises(DagCborError):
                    decode(bytes.fromhex(head + filler))

    def test_other_simple_values_rejected_on_decode(self) -> None:
        # undefined (0xf7) and unassigned simple values are banned.
        for hx in ("f7", "f820"):
            with self.subTest(hx=hx):
                with self.assertRaises(DagCborError):
                    decode(bytes.fromhex(hx))

    def test_bytes(self) -> None:
        self.assertEqual(hex_of(b""), "40")
        self.assertEqual(hex_of(b"\x01\x02"), "420102")
        chunk = bytes(range(256))  # length 256 needs the 2-byte form (0x59 0x0100)
        self.assertEqual(
            hex_of(chunk),
            "590100" + chunk.hex(),
        )

    def test_text(self) -> None:
        self.assertEqual(hex_of(""), "60")
        self.assertEqual(hex_of("a"), "6161")
        self.assertEqual(hex_of("IETF"), "6449455446")
        self.assertEqual(hex_of("é"), "62c3a9")
        self.assertEqual(decode(encode("éé")), "éé")

    def test_invalid_utf8_rejected_on_decode(self) -> None:
        with self.assertRaises(DagCborError):
            decode(bytes.fromhex("62c328"))


class TestCanonicalStructures(unittest.TestCase):
    def test_map_sorted_bytewise(self) -> None:
        # 'a' (0x61) sorts before 'é' (0xc3 0xa9): keys compare by UTF-8 bytes.
        self.assertEqual(hex_of({"a": 1, "é": 2}), "a2" + "6161" + "01" + "62c3a9" + "02")

    def test_map_key_order_matches_bytewise_not_first_insertion(self) -> None:
        forward = {"b": 1, "a": 2}
        backward = {"a": 2, "b": 1}
        self.assertEqual(encode(forward), encode(backward))
        self.assertEqual(decode(encode(forward)), {"a": 2, "b": 1})

    def test_nested_pieces(self) -> None:
        self.assertEqual(hex_of({"a": 1}), "a1" + "6161" + "01")
        self.assertEqual(hex_of({"a": [1, 2]}), "a1" + "6161" + "820102")
        self.assertEqual(hex_of({"b": {"c": None}}), "a1" + "6162" + "a16163" + "f6")
        self.assertEqual(
            hex_of({"d": True, "e": "é"}),
            "a2" + "6164" + "f5" + "6165" + "62c3a9",
        )
        value = {"a": [1, 2], "b": {"c": None}, "d": True, "e": "é"}
        self.assertEqual(decode(encode(value)), value)

    def test_empty_containers(self) -> None:
        self.assertEqual(hex_of([]), "80")
        self.assertEqual(hex_of({}), "a0")
        self.assertEqual(decode(bytes.fromhex("80")), [])
        self.assertEqual(decode(bytes.fromhex("a0")), {})

    def test_map_keys_must_be_strings(self) -> None:
        for bad in ({"a": 1, 5: 2}, {None: 1}, {b"x": 1}):
            with self.subTest(bad=bad):
                with self.assertRaises(DagCborError):
                    encode(bad)
        with self.assertRaises(DagCborError):
            decode(bytes.fromhex("a106" + "01"))  # integer-keyed map

    def test_cbor_tag_other_than_42_rejected_on_decode(self) -> None:
        with self.assertRaises(DagCborError):
            decode(bytes.fromhex("c000"))  # tag 0


class TestLinkEncoding(unittest.TestCase):
    def test_cid_encodes_as_tag_42_with_identity_prefix(self) -> None:
        cid = Cid.of_bytes(MULTICODEC_RAW, b"payload")
        encoded = encode({"link": cid})
        # {"link": <cid>} → a1 64 'link' d8 2a (tag 42) 58 25 00 <36 CID bytes>
        head = bytes.fromhex("a1646c696e6bd82a5825")
        self.assertTrue(encoded.startswith(head))
        self.assertEqual(bytes(encoded[len(head):]), b"\x00" + cid.cid_bytes())
        decoded = decode(encoded)
        self.assertIsInstance(decoded["link"], Cid)
        self.assertEqual(decoded["link"], cid)
        self.assertEqual(decoded["link"].cid_bytes(), cid.cid_bytes())

    def test_cid_is_canonical_stable(self) -> None:
        cid = Cid.of_bytes(MULTICODEC_RAW, b"stable")
        encoded = encode({"x": cid})
        self.assertTrue(is_canonical(encoded))


class TestStrictDecoder(unittest.TestCase):
    def test_trailing_bytes_rejected(self) -> None:
        with self.assertRaises(DagCborError):
            decode(bytes.fromhex("6161" + "00"))

    def test_indefinite_length_rejected(self) -> None:
        with self.assertRaises(DagCborError):
            decode(bytes.fromhex("9fff"))  # indefinite array

    def test_non_minimal_int_rejected(self) -> None:
        # text "a" then int 1 padded into a 2-byte form (non-minimal)
        with self.assertRaises(DagCborError):
            decode(bytes.fromhex("6161" + "190001"))


class TestIsCanonicalHelper(unittest.TestCase):
    def test_canonical_bytes_accept(self) -> None:
        self.assertTrue(is_canonical(encode("hello")))
        self.assertTrue(is_canonical(encode({"a": 1, "b": []})))
        self.assertTrue(is_canonical(encode(2**64 - 1)))

    def test_non_canonical_bytes_reject(self) -> None:
        # 0x19000a: unsigned 10 encoded in the 2-byte form — non-minimal,
        # valid plain CBOR but not canonical DAG-CBOR.
        self.assertFalse(is_canonical(bytes.fromhex("19000a")))
