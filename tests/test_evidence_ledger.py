"""Unit tests for the dependency-free Evidence Ledger validator."""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evidence_ledger as el  # noqa: E402


def valid_doc() -> dict:
    return el.ledger_document(
        ledger_id="test-ledger",
        decision="Should we?",
        prepared_by="tester",
        freeze_time_utc="2026-06-01T00:00:00Z",
        sensitivity="public",
        entries=[
            {
                "id": "E1",
                "item": "A fact.",
                "source_type": "policy",
                "source": "src",
                "provenance": "prov",
                "handling": "quote exact text",
            }
        ],
    )


class EvidenceLedgerTests(unittest.TestCase):
    def test_valid_document_passes(self):
        self.assertEqual(el.validate_ledger_document(valid_doc()), [])

    def test_demo_ledgers_pass(self):
        for path in sorted((ROOT / "demos" / "evidence-ledgers").glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(el.validate_ledger_document(document), [], f"{path.name} should validate")

    def test_missing_required_field_fails(self):
        doc = valid_doc()
        del doc["decision"]
        failures = el.validate_ledger_document(doc)
        self.assertTrue(any("decision" in f for f in failures))

    def test_required_arrays_are_enforced(self):
        # Aligns the dependency-free validator with the JSON schema's required arrays.
        for key in ("open_evidence_gaps", "redactions"):
            doc = valid_doc()
            del doc[key]
            failures = el.validate_ledger_document(doc)
            self.assertTrue(any(key in f for f in failures), f"{key} should be required")

    def test_non_contiguous_ids_fail(self):
        doc = valid_doc()
        doc["entries"] = [
            copy.deepcopy(doc["entries"][0]),
            {**copy.deepcopy(doc["entries"][0]), "id": "E3"},
        ]
        failures = el.validate_ledger_document(doc)
        self.assertTrue(any("contiguous" in f for f in failures))

    def test_duplicate_ids_fail(self):
        doc = valid_doc()
        doc["entries"] = [copy.deepcopy(doc["entries"][0]), copy.deepcopy(doc["entries"][0])]
        failures = el.validate_ledger_document(doc)
        self.assertTrue(any("duplicate evidence id" in f for f in failures))

    def test_bad_content_hash_fails(self):
        doc = valid_doc()
        doc["entries"][0]["content_hash"] = "not-a-hash"
        failures = el.validate_ledger_document(doc)
        self.assertTrue(any("content_hash" in f for f in failures))

    def test_bad_source_type_fails(self):
        doc = valid_doc()
        doc["entries"][0]["source_type"] = "rumor"
        failures = el.validate_ledger_document(doc)
        self.assertTrue(any("source_type" in f for f in failures))

    def test_bad_timestamp_fails(self):
        doc = valid_doc()
        doc["freeze_time_utc"] = "2026-06-01 00:00:00"
        failures = el.validate_ledger_document(doc)
        self.assertTrue(any("freeze_time_utc" in f for f in failures))


if __name__ == "__main__":
    unittest.main()
