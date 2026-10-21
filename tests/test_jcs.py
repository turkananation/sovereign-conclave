"""Tests for the non-normative JCS-JSON view (conclave_core.jcs)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conclave_core.jcs import JcsError, jcs, jcs_bytes


class TestJcsBasics(unittest.TestCase):
    def test_scalars(self) -> None:
        self.assertEqual(jcs(None), "null")
        self.assertEqual(jcs(True), "true")
        self.assertEqual(jcs(False), "false")
        self.assertEqual(jcs(0), "0")
        self.assertEqual(jcs(-1), "-1")
        self.assertEqual(jcs(2**64 - 1), str(2**64 - 1))
        self.assertEqual(jcs("plain"), '"plain"')

    def test_string_escaping(self) -> None:
        self.assertEqual(jcs('say "hi"'), '"say \\"hi\\""')
        self.assertEqual(jcs("back\\slash"), '"back\\\\slash"')
        self.assertEqual(jcs("tab\there"), '"tab\\there"')
        self.assertEqual(jcs("new\nline"), '"new\\nline"')
        self.assertEqual(jcs("\u0001"), '"\\u0001"')
        self.assertEqual(jcs("\u001f"), '"\\u001f"')

    def test_unicode_kept_literal(self) -> None:
        # JCS emits non-ASCII literally (UTF-8 on the wire)
        self.assertEqual(jcs("é"), '"é"')
        self.assertEqual(jcs_bytes("é"), '"é"'.encode("utf-8"))

    def test_map_members_sorted_no_whitespace(self) -> None:
        self.assertEqual(jcs({"b": [1, 2], "a": 1}), '{"a":1,"b":[1,2]}')
        shuffled = {"b": [1, 2], "a": 1}
        ordered = {"a": 1, "b": [1, 2]}
        self.assertEqual(jcs(shuffled), jcs(ordered))
        self.assertEqual(jcs({}), "{}")
        self.assertEqual(jcs([]), "[]")

    def test_utf16_code_unit_key_order(self) -> None:
        # RFC 8785 sorts by UTF-16 code units; an astral-plane key sorts
        # BEFORE U+FFFF even though its code point is larger.
        ordered = {"\U0001f600": 1, "\uffff": 2}
        expected = '{"\U0001f600":1,"\uffff":2}'
        self.assertEqual(jcs(ordered), expected)

    def test_nested_minimality(self) -> None:
        value = {"a": [1, {"b": None, "c": True}], "d": "x"}
        parsed = json.loads(jcs(value))
        self.assertEqual(parsed, value)
        self.assertNotIn(" ", jcs(value))

    def test_floats_banned(self) -> None:
        with self.assertRaises(JcsError):
            jcs(1.5)
        with self.assertRaises(JcsError):
            jcs({"x": [2.5]})

    def test_bytes_rejected(self) -> None:
        with self.assertRaises(JcsError):
            jcs(b"raw")

    def test_jcs_bytes_utf8(self) -> None:
        self.assertEqual(jcs_bytes({"k": "é"}), '{"k":"é"}'.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
