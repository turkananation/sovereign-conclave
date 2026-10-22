"""M7 export tests: ADR markdown, JSON-LD, signed HTML, and refusal paths.

The export tool's core promise: it renders ONLY verifier-clean bundles,
deterministically, with no wall-clock or host data — so the same bundle
bytes always render the same decision record.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "scripts"), str(ROOT / "tests")):
    if path not in sys.path:
        sys.path.insert(0, path)

from scripts.artifact_emitter import CaseSeed, emit_case_bundle  # noqa: E402
from scripts.verdict_export import (  # noqa: E402
    DEFAULT_VERIFY_ENDPOINT,
    ExportError,
    export_all,
    load_case,
    main,
    render_adr,
    render_html,
    render_jsonld,
)
from test_emit_bundle import LEDGER_ENTRIES, ROSTER  # canonical emit fixtures

TIME = "2026-10-21T09:00:00Z"


def scaffold_bundle(root: Path, *, timestamp=TIME, problem="Should we split the analytics service?") -> Path:
    seed = CaseSeed(
        profile_id="architecture",
        problem=problem,
        timestamp=timestamp,
        seats=["conclave-feynman", "conclave-zhukov"],
        marshall_id="conclave-marshall",
        roster=ROSTER,
        ledger_entries=LEDGER_ENTRIES,
        transcript=None,
    )
    bundle, _fingerprint = emit_case_bundle(seed, root / "case", root / "keys")
    return bundle


class VerdictExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.bundle = scaffold_bundle(self.root)
        self.out = self.root / "out"
        self.written = export_all(
            self.bundle, self.out, ["adr", "jsonld", "html"], DEFAULT_VERIFY_ENDPOINT
        )
        names = {path.name for path in self.written}
        self.assertEqual(
            names, {"decision-record.md", "decision-record.jsonld", "decision-record.html"}
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @property
    def adr(self) -> str:
        return (self.out / "decision-record.md").read_text(encoding="utf-8")

    @property
    def jsonld(self) -> dict:
        return json.loads(
            (self.out / "decision-record.jsonld").read_text(encoding="utf-8")
        )

    @property
    def html(self) -> str:
        return (self.out / "decision-record.html").read_text(encoding="utf-8")

    def test_load_case_only_accepts_verified_bundles(self):
        store, config = load_case(self.bundle)
        self.assertEqual(config["version"], 1)
        self.assertTrue(store)

        tampered = scaffold_bundle(self.root, problem="Second case for tampering")
        target = next(iter((tampered / "artifacts").glob("*.cbor")))
        target.write_bytes(target.read_bytes()[:-2] + b"xx")
        with self.assertRaises(ExportError) as caught:
            load_case(tampered)
        self.assertIn("refusing to export", str(caught.exception))

    def test_adr_carries_decision_evidence_and_verification(self):
        self.assertIn("# Conclave Decision Record", self.adr)
        self.assertIn("**Status: advised (non-binding).**", self.adr)
        self.assertIn("## Decision", self.adr)
        self.assertIn("### Recorded vote", self.adr)
        self.assertIn("## Evidence ledger", self.adr)
        self.assertIn("| E1 |", self.adr)
        self.assertIn("## Transparency and verification", self.adr)
        self.assertIn("- **Log head:** size 1", self.adr)
        self.assertIn("python3 -m conclave_core.verifier", self.adr)

    def test_jsonld_is_strict_json_with_cids_and_log(self):
        record = self.jsonld
        self.assertEqual(record["@type"], ["conclave:Decision", "https://schema.org/Conclusion"])
        self.assertTrue(record["@id"].startswith("urn:conclave:cid:"))
        self.assertEqual(record["conclave:logHead"]["treeSize"], 1)
        leaf_types = {leaf["artifactType"] for leaf in record["conclave:logLeaves"]}
        self.assertIn("Verdict", leaf_types)
        self.assertEqual(record["conclave:question"]["text"], "Should we split the analytics service?")
        self.assertIn(record["conclave:status"], {"advised-non-binding"})

    def test_html_is_selfcontained_and_carries_the_verify_url(self):
        self.assertTrue(self.html.startswith("<!DOCTYPE html>"))
        self.assertNotIn("<link ", self.html)          # no external stylesheets
        self.assertNotIn("<iframe", self.html)         # nothing remote
        self.assertIn("python3 -m conclave_core.verifier", self.html)
        self.assertIn(DEFAULT_VERIFY_ENDPOINT, self.html)
        # the embedded QR must be valid XML when present (optional extra)
        if "<svg" in self.html:
            start = self.html.index("<div class=\"qr\">") + len("<div class=\"qr\">")
            end = self.html.index("</div>", start)
            xml.etree.ElementTree.fromstring(self.html[start:end])

    def test_render_is_deterministic_across_calls(self):
        before = {path.name: path.read_bytes() for path in self.out.iterdir()}
        export_all(
            self.bundle, self.root / "out2", ["adr", "jsonld", "html"],
            DEFAULT_VERIFY_ENDPOINT,
        )
        after = {path.name: path.read_bytes() for path in (self.root / "out2").iterdir()}
        self.assertEqual(before, after)

    def test_verifier_findings_refuse_every_format(self):
        tampered = scaffold_bundle(self.root, problem="refusal probe")
        target = next(iter((tampered / "artifacts").glob("*.cbor")))
        target.write_bytes(target.read_bytes()[:-2] + b"xx")
        with self.assertRaises(ExportError):
            export_all(tampered, self.root / "no-out", ["html"], DEFAULT_VERIFY_ENDPOINT)

    def test_pdf_needs_the_weasyprint_extra_when_absent(self):
        with patch.dict(sys.modules, {"weasyprint": None}):
            with self.assertRaises(ExportError) as caught:
                export_all(
                    self.bundle, self.root / "pdf-out", ["html", "pdf"],
                    DEFAULT_VERIFY_ENDPOINT,
                )
        self.assertIn("WeasyPrint", str(caught.exception))
        self.assertIn("stdlib baseline", str(caught.exception))

    def test_cli_module_entrypoint(self):
        with patch.object(sys, "argv", ["verdict_export", "--help"]):
            with self.assertRaises(SystemExit) as caught:
                main()  # argparse help exit
        self.assertEqual(caught.exception.code, 0)

    def test_cli_refuses_unknown_format(self):
        with patch.object(
            sys, "argv",
            ["verdict_export", str(self.bundle), "--out-dir", str(self.root / "x"),
             "--formats", "pptx"],
        ):
            with self.assertRaises(SystemExit):
                main()

    def test_renders_directly_match_export_writes(self):
        store, config = load_case(self.bundle)
        self.assertEqual(
            render_adr(store, config, self.bundle, DEFAULT_VERIFY_ENDPOINT), self.adr
        )
        self.assertEqual(
            render_jsonld(store, config, self.bundle, DEFAULT_VERIFY_ENDPOINT),
            (self.out / "decision-record.jsonld").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            render_html(store, config, self.bundle, DEFAULT_VERIFY_ENDPOINT), self.html
        )


if __name__ == "__main__":
    unittest.main()
