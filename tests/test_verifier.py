"""End-to-end tests: synthetic case bundle -> offline verification.

The fixture exercises every M2 verifier stage: artifact integrity, DAG
verification, the signature chain (identity, orchestrator certificate,
round attestation, persona-registry, possession proofs), and the RFC 6962
transparency log (tree heads, consistency, inclusion).
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conclave_core.artifacts import (
    artifact_bytes,
    artifact_cid,
    make_evidence_ledger,
    make_manifest,
    make_panel,
    make_persona,
    make_protocol_params,
    make_question,
    make_round,
    make_summary,
    make_turn,
    make_verdict,
    raw_cid,
)
from conclave_core.merkle import consistency_proof, path, tree_hash
from conclave_core.signing import (
    DOMAIN_LOG_STH,
    DOMAIN_PERSONA_MANIFEST,
    DOMAIN_ROUND_ATTESTATION,
    DOMAIN_VERDICT,
    make_certificate_signed,
    make_key_publication_signed,
    make_signature_signed,
    make_signed_tree_head_signed,
)
from conclave_core.verifier import BUNDLE_VERSION, verify_bundle

IDENTITY_SEED = hashlib.sha256(b"conclave-test/e2e/identity").digest()
ORCHESTRATOR_SEED = hashlib.sha256(b"conclave-test/e2e/orchestrator").digest()
REGISTRY_SEED = hashlib.sha256(b"conclave-test/e2e/registry").digest()

LEDGER_ENTRIES = [
    {
        "id": "E1",
        "item": "The validation stack was green on 2026-10-01.",
        "provenance": {"source": "CI run log", "kind": "command output"},
        "handling": "primary source",
    },
    {
        "id": "E2",
        "item": "The extraction plan was reviewed by the platform team.",
        "provenance": {"source": "docs/extraction-plan.md", "kind": "local file"},
        "handling": "local file",
    },
]


def _persona(seat_id: str, display: str, model: str) -> dict:
    return make_persona(
        seat_id=seat_id,
        display_name=display,
        tier="General",
        lens=f"{display} lens",
        stance=f"{display} argues from delivery concerns.",
        how_you_argue=[
            "Names the decisive evidence first.",
            "Concedes when the ledger contradicts the stance.",
        ],
        characteristic_bias=f"Overweights {display} framing.",
        is_not=["Not any other seat."],
        model=model,
        version="roster-0.1.0",
    )


def build_signed_case(*, sign_verdict_b: bool = True) -> tuple[list[dict], dict]:
    """Build a fully signed two-verdict case bundle (artifacts + bundle.json)."""

    question = make_question(
        "Should we split the analytics service?",
        options=[
            {"id": "split", "label": "Split into its own service"},
            {"id": "keep", "label": "Keep in the monolith"},
        ],
        asked_by="platform team",
        asked_at="2026-10-01T09:00:00Z",
    )
    ledger = make_evidence_ledger(LEDGER_ENTRIES, created_at="2026-10-01T09:05:00Z")
    personas = [
        _persona("conclave-feynman", "Richard Feynman", "sonnet"),
        _persona("conclave-zhukov", "Georgy Zhukov", "sonnet"),
        _persona("conclave-washington", "George Washington", "sonnet"),
        _persona("conclave-marshall", "Marshall", "opus"),
    ]
    panel = make_panel(
        [
            {
                "seatId": persona["seatId"],
                "persona": artifact_cid(persona),
                "model": persona["model"],
            }
            for persona in personas
        ],
        convened_at="2026-10-01T09:10:00Z",
        quorum=3,
    )
    params = make_protocol_params(recorded_by="session-orchestrator", quorum=3)

    manifest_v1 = make_manifest(
        case_id="case-2026-10-01-analytics",
        question=artifact_cid(question),
        evidence_ledger=artifact_cid(ledger),
        panel=artifact_cid(panel),
        protocol_params=artifact_cid(params),
        title="Analytics service split",
        opened_at="2026-10-01T09:00:30Z",
    )

    first_turn = make_turn(
        round_index=0,
        seat_id="conclave-feynman",
        persona=artifact_cid(personas[0]),
        input_context_hash=raw_cid(b"prompt-feynman"),
        model_id="claude-sonnet-4",
        output=raw_cid(b"output-feynman"),
        citations=["E2"],
        tokens={"inputTokens": 900, "outputTokens": 340},
        recorded_at="2026-10-01T09:20:00Z",
        provider_run=False,
    )
    second_turn = make_turn(
        round_index=0,
        seat_id="conclave-zhukov",
        persona=artifact_cid(personas[1]),
        input_context_hash=raw_cid(b"prompt-zhukov"),
        model_id="claude-sonnet-4",
        output=raw_cid(b"output-zhukov"),
        citations=["E1", "E2"],
        tokens={"inputTokens": 900, "outputTokens": 340},
        recorded_at="2026-10-01T09:21:00Z",
        provider_run=False,
    )
    turn_cids = [artifact_cid(first_turn), artifact_cid(second_turn)]
    summary = make_summary(
        round_index=0,
        distilled_from=turn_cids,
        positions=[
            {"seatId": "conclave-feynman", "stance": "split", "citations": ["E2"]},
            {"seatId": "conclave-zhukov", "stance": "keep", "citations": ["E1", "E2"]},
        ],
        summary_text="Two seats favor the split; Zhukov resists on readiness.",
        written_at="2026-10-01T09:30:00Z",
        model_id="haiku-class",
        word_count=12,
    )
    round_zero = make_round(
        index=0,
        prev=None,
        status="committed",
        participants=["conclave-feynman", "conclave-zhukov", "conclave-washington"],
        turns=turn_cids,
        distilled_summary=artifact_cid(summary),
        opened_at="2026-10-01T09:10:00Z",
        closed_at="2026-10-01T09:35:00Z",
    )
    round_zero_cid = artifact_cid(round_zero)

    manifest_v2 = make_manifest(
        case_id="case-2026-10-01-analytics",
        question=artifact_cid(question),
        evidence_ledger=artifact_cid(ledger),
        panel=artifact_cid(panel),
        protocol_params=artifact_cid(params),
        rounds=[round_zero_cid],
        supersedes=artifact_cid(manifest_v1),
        title="Analytics service split",
        opened_at="2026-10-01T09:00:30Z",
    )
    verdict_a = make_verdict(
        manifest=artifact_cid(manifest_v2),
        final_round=round_zero_cid,
        decision="Split the analytics service behind a feature-flagged extraction.",
        recommendation=(
            "The Sovereign Conclave advises you to run a 30-day flagged extraction "
            "of the analytics service before committing."
        ),
        votes=[
            {
                "seatId": persona["seatId"],
                "persona": artifact_cid(persona),
                "stance": "split",
                "weightMicro": 1_000_000,
            }
            for persona in personas
        ],
        confidence="medium",
        issued_at="2026-10-01T10:00:00Z",
    )
    manifest_final = make_manifest(
        case_id="case-2026-10-01-analytics",
        question=artifact_cid(question),
        evidence_ledger=artifact_cid(ledger),
        panel=artifact_cid(panel),
        protocol_params=artifact_cid(params),
        rounds=[round_zero_cid],
        verdict=artifact_cid(verdict_a),
        supersedes=artifact_cid(manifest_v2),
        title="Analytics service split",
        opened_at="2026-10-01T09:00:30Z",
    )

    # a second case's verdict, published to the same transparency log
    manifest_b = make_manifest(
        case_id="case-2026-10-02-service-owner",
        question=artifact_cid(question),
        evidence_ledger=artifact_cid(ledger),
        panel=artifact_cid(panel),
        protocol_params=artifact_cid(params),
        title="Service owner election",
        opened_at="2026-10-02T09:00:00Z",
    )
    verdict_b = make_verdict(
        manifest=artifact_cid(manifest_b),
        final_round=round_zero_cid,
        decision="Elect the platform team as service owner.",
        recommendation="The Sovereign Conclave advises you to elect the platform team.",
        votes=[
            {
                "seatId": persona["seatId"],
                "persona": artifact_cid(persona),
                "stance": "platform-team",
                "weightMicro": 1_000_000,
            }
            for persona in personas
        ],
        confidence="high",
        issued_at="2026-10-02T10:00:00Z",
    )

    artifacts: list[dict] = [
        question, ledger, panel, params,
        manifest_v1, manifest_v2, manifest_final,
        first_turn, second_turn, summary, round_zero, verdict_a,
        manifest_b, verdict_b,
        *personas,
    ]

    # ---- signing chain ---------------------------------------------------
    identity_kp, identity_possession = make_key_publication_signed(
        seed=IDENTITY_SEED, role="identity", published_at="2026-01-01T00:00:00Z"
    )
    registry_kp, registry_possession = make_key_publication_signed(
        seed=REGISTRY_SEED, role="persona-registry", published_at="2026-01-01T00:00:00Z"
    )
    orch_kp, certificate, cert_sig = make_certificate_signed(
        orchestrator_seed=ORCHESTRATOR_SEED,
        identity_seed=IDENTITY_SEED,
        case_manifest=artifact_cid(manifest_v2),
        issued_at="2026-10-01T09:01:00Z",
    )
    orch_possession = make_signature_signed(
        seed=ORCHESTRATOR_SEED,
        domain="orchestrator",
        payload=artifact_cid(orch_kp),
        signed_at="2026-10-01T09:01:00Z",
    )
    verdict_a_sig = make_signature_signed(
        seed=IDENTITY_SEED, domain=DOMAIN_VERDICT, payload=artifact_cid(verdict_a)
    )
    artifacts += [
        identity_kp, identity_possession,
        registry_kp, registry_possession,
        orch_kp, orch_possession, certificate, cert_sig,
        verdict_a_sig,
    ]
    if sign_verdict_b:
        artifacts.append(
            make_signature_signed(
                seed=IDENTITY_SEED, domain=DOMAIN_VERDICT, payload=artifact_cid(verdict_b)
            )
        )
    artifacts.append(
        make_signature_signed(
            seed=ORCHESTRATOR_SEED,
            domain=DOMAIN_ROUND_ATTESTATION,
            payload=round_zero_cid,
            signed_at="2026-10-01T09:35:30Z",
        )
    )
    for persona in personas:
        artifacts.append(
            make_signature_signed(
                seed=REGISTRY_SEED,
                domain=DOMAIN_PERSONA_MANIFEST,
                payload=artifact_cid(persona),
            )
        )

    # ---- transparency log ------------------------------------------------
    leaf_a = artifact_cid(verdict_a)
    leaf_b = artifact_cid(verdict_b)
    leaves = [leaf_a.cid_bytes(), leaf_b.cid_bytes()]
    sth_one, sth_one_sig = make_signed_tree_head_signed(
        log_id="conclave-test-log",
        tree_size=1,
        root_hash=tree_hash(leaves[:1]),
        seed=IDENTITY_SEED,
        published_at="2026-10-01T10:05:00Z",
    )
    sth_two, sth_two_sig = make_signed_tree_head_signed(
        log_id="conclave-test-log",
        tree_size=2,
        root_hash=tree_hash(leaves),
        seed=IDENTITY_SEED,
        published_at="2026-10-02T10:05:00Z",
    )
    artifacts += [sth_one, sth_one_sig, sth_two, sth_two_sig]

    config = {
        "version": BUNDLE_VERSION,
        "manifestCid": str(artifact_cid(manifest_final)),
        "expectedIdentityFingerprint": identity_kp["keyFingerprint"],
        "expectedRegistryFingerprint": registry_kp["keyFingerprint"],
        "log": {
            "leaves": [str(leaf_a), str(leaf_b)],
            "sthCids": [str(artifact_cid(sth_one)), str(artifact_cid(sth_two))],
            "consistency": [
                {
                    "first": 1,
                    "second": 2,
                    "path": [
                        base64.b64encode(node).decode()
                        for node in consistency_proof(1, leaves)
                    ],
                }
            ],
            "inclusion": {
                str(leaf_a): {
                    "index": 0,
                    "treeSize": 2,
                    "path": [
                        base64.b64encode(node).decode()
                        for node in path(0, [leaf_a.cid_bytes(), leaf_b.cid_bytes()])
                    ],
                },
                str(leaf_b): {
                    "index": 1,
                    "treeSize": 2,
                    "path": [
                        base64.b64encode(node).decode()
                        for node in path(1, [leaf_a.cid_bytes(), leaf_b.cid_bytes()])
                    ],
                },
            },
        },
    }
    return artifacts, config


def write_bundle(directory: Path, artifacts: list[dict], config: dict) -> None:
    (directory / "artifacts").mkdir(parents=True, exist_ok=True)
    for artifact in artifacts:
        cid = artifact_cid(artifact)
        (directory / "artifacts" / f"{cid}.cbor").write_bytes(artifact_bytes(artifact))
    (directory / "bundle.json").write_text(
        json.dumps(config, indent=2, sort_keys=True), encoding="utf-8"
    )


def fresh_case(self: unittest.TestCase):
    artifacts, config = build_signed_case()
    bundle_dir = Path(self.enterContext(tempfile.TemporaryDirectory())) / "case"
    bundle_dir = bundle_dir.resolve()
    write_bundle(bundle_dir, artifacts, config)
    return bundle_dir, artifacts, config


class TestCleanBundle(unittest.TestCase):
    def test_verify_bundle_accepts_a_valid_bundle(self) -> None:
        bundle_dir, _, _ = fresh_case(self)
        problems, summary = verify_bundle(bundle_dir)
        self.assertEqual(problems, [], msg="\n".join(problems))
        self.assertEqual(summary["status"], "VERIFIED")

    def test_cli_exit_zero_and_human_summary(self) -> None:
        bundle_dir, _, _ = fresh_case(self)
        result = subprocess.run(
            [sys.executable, "-m", "conclave_core.verifier", str(bundle_dir)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("VERIFIED", result.stdout)
        json_result = subprocess.run(
            [sys.executable, "-m", "conclave_core.verifier", str(bundle_dir), "--json"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json.loads(json_result.stdout)["status"], "VERIFIED")


class TestTamperDetection(unittest.TestCase):
    """Each test perturbs a copied bundle; the verifier must flag it."""

    def _copied_case(self) -> tuple[Path, list[dict], dict]:
        bundle_dir, artifacts, config = fresh_case(self)
        corrupt_dir = Path(self.enterContext(tempfile.TemporaryDirectory())) / "corrupt"
        corrupt_dir = corrupt_dir.resolve()
        shutil.copytree(bundle_dir, corrupt_dir)
        return corrupt_dir, artifacts, config

    @staticmethod
    def _rewrite_config(corrupt_dir: Path, config: dict) -> None:
        (corrupt_dir / "bundle.json").write_text(
            json.dumps(config, indent=2, sort_keys=True), encoding="utf-8"
        )

    def test_corrupted_artifact_content_detected(self) -> None:
        corrupt_dir, artifacts, _ = self._copied_case()
        verdict = next(a for a in artifacts if a.get("type") == "Verdict"
                       and "advises you to run" in a["recommendation"])
        tampered = dict(verdict)
        tampered["decision"] = "Rigged decision."
        (corrupt_dir / "artifacts" / f"{artifact_cid(verdict)}.cbor").write_bytes(
            artifact_bytes(tampered)
        )
        problems, _ = verify_bundle(corrupt_dir)
        self.assertTrue(any("content hashes" in p for p in problems), msg=str(problems))

    def test_wrong_identity_pin_detected(self) -> None:
        corrupt_dir, _, config = self._copied_case()
        config["expectedIdentityFingerprint"] = "a" * 64
        self._rewrite_config(corrupt_dir, config)
        problems, _ = verify_bundle(corrupt_dir)
        self.assertTrue(
            any("verdict signature" in p and "not the expected" in p for p in problems),
            msg=str(problems),
        )

    def test_missing_round_attestation_detected(self) -> None:
        corrupt_dir, artifacts, _ = self._copied_case()
        attestation = next(
            a for a in artifacts if a.get("type") == "Signature"
            and a["domain"] == DOMAIN_ROUND_ATTESTATION
        )
        (corrupt_dir / "artifacts" / f"{artifact_cid(attestation)}.cbor").unlink()
        problems, _ = verify_bundle(corrupt_dir)
        self.assertTrue(
            any("no valid orchestrator round attestation" in p for p in problems),
            msg=str(problems),
        )

    def test_orchestrator_possession_proof_removed_detected(self) -> None:
        corrupt_dir, artifacts, _ = self._copied_case()
        orch_key = next(
            a for a in artifacts if a.get("type") == "KeyPublication"
            and a["role"] == "orchestrator"
        )
        possession = next(
            a for a in artifacts if a.get("type") == "Signature"
            and a["domain"] == "orchestrator"
        )
        (corrupt_dir / "artifacts" / f"{artifact_cid(possession)}.cbor").unlink()
        problems, _ = verify_bundle(corrupt_dir)
        self.assertTrue(
            any(str(artifact_cid(orch_key)) in p and "possession" in p for p in problems),
            msg=str(problems),
        )

    def test_case_verdict_must_appear_in_log_leaves(self) -> None:
        corrupt_dir, _, config = self._copied_case()
        config["log"]["leaves"] = config["log"]["leaves"][1:]
        self._rewrite_config(corrupt_dir, config)
        problems, _ = verify_bundle(corrupt_dir)
        self.assertTrue(
            any("not published in the bundle's" in p for p in problems), msg=str(problems)
        )

    def test_unsigned_verdict_in_log_rejected(self) -> None:
        bundle_dir = Path(self.enterContext(tempfile.TemporaryDirectory())) / "case"
        bundle_dir = bundle_dir.resolve()
        artifacts, config = build_signed_case(sign_verdict_b=False)
        write_bundle(bundle_dir, artifacts, config)
        problems, _ = verify_bundle(bundle_dir)
        self.assertTrue(
            any("not signed by the expected identity key" in p for p in problems),
            msg=str(problems),
        )

    def test_wrong_registry_pin_detected(self) -> None:
        corrupt_dir, _, config = self._copied_case()
        config["expectedRegistryFingerprint"] = "b" * 64
        self._rewrite_config(corrupt_dir, config)
        problems, _ = verify_bundle(corrupt_dir)
        self.assertTrue(
            any("not signed by the expected persona-registry" in p for p in problems),
            msg=str(problems),
        )

    def test_inconsistent_log_root_detected(self) -> None:
        corrupt_dir, artifacts, config = self._copied_case()
        sth_two = next(
            a for a in artifacts if a.get("type") == "SignedTreeHead" and a["treeSize"] == 2
        )
        fake = dict(sth_two)
        fake["rootHash"] = hashlib.sha256(b"attacker-root").digest()
        fake_name = artifact_cid(fake)
        target = corrupt_dir / "artifacts" / f"{artifact_cid(sth_two)}.cbor"
        target.unlink()
        (corrupt_dir / "artifacts" / f"{fake_name}.cbor").write_bytes(artifact_bytes(fake))
        config["log"]["sthCids"] = [
            c if c != str(artifact_cid(sth_two)) else str(fake_name)
            for c in config["log"]["sthCids"]
        ]
        self._rewrite_config(corrupt_dir, config)
        problems, _ = verify_bundle(corrupt_dir)
        self.assertTrue(
            any("leaves hash to" in p for p in problems), msg=str(problems)
        )
        self.assertTrue(
            any("does not verify" in p for p in problems), msg=str(problems)
        )


if __name__ == "__main__":
    unittest.main()
