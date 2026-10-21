"""Tests for signing conventions and signed-artifact builders."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conclave_core.artifacts import (
    ArtifactError,
    TYPE_CERTIFICATE,
    TYPE_KEY_PUBLICATION,
    TYPE_SIGNATURE,
    artifact_cid,
    make_question,
    validate_artifact,
)
from conclave_core.signing import (
    DOMAIN_CERTIFY_ORCHESTRATOR,
    DOMAIN_LOG_STH,
    DOMAIN_VERDICT,
    context_for,
    make_certificate_signed,
    make_key_publication_signed,
    make_signature_signed,
    make_signed_tree_head_signed,
    select_signatures,
    signature_message,
    sign_cid,
    verify_signature_artifact,
)
from conclave_core.mldsa import keygen, keypair_from_seed, verify

IDENTITY_SEED = hashlib.sha256(b"conclave-test/signing/identity").digest()
ORCHESTRATOR_SEED = hashlib.sha256(b"conclave-test/signing/orchestrator").digest()


class TestConventions(unittest.TestCase):
    def test_context_for(self) -> None:
        self.assertEqual(context_for(DOMAIN_VERDICT), b"conclave/verdict/v1")
        self.assertEqual(context_for(DOMAIN_LOG_STH), b"conclave/log-sth/v1")
        with self.assertRaises(ValueError):
            context_for("x" * 300)

    def test_signature_message_is_raw_cid(self) -> None:
        question = make_question("q", asked_by="t")
        cid = artifact_cid(question)
        self.assertEqual(signature_message(cid), cid.cid_bytes())

    def test_sign_cid_verifies_only_for_matching_domain(self) -> None:
        question = make_question("q", asked_by="t")
        cid = artifact_cid(question)
        signature = sign_cid(IDENTITY_SEED, DOMAIN_VERDICT, cid)
        _, public_key = keypair_from_seed(IDENTITY_SEED)
        self.assertTrue(verify(public_key, cid.cid_bytes(), signature, context=context_for(DOMAIN_VERDICT)))
        self.assertFalse(verify(public_key, cid.cid_bytes(), signature, context=context_for(DOMAIN_LOG_STH)))


class TestBuilders(unittest.TestCase):
    def test_key_publication_signed_has_possession_proof(self) -> None:
        publication, possession = make_key_publication_signed(
            seed=IDENTITY_SEED, role="identity", published_at="2026-02-01T00:00:00Z"
        )
        validate_artifact(publication)
        validate_artifact(possession)
        self.assertEqual(publication["type"], TYPE_KEY_PUBLICATION)
        self.assertEqual(possession["type"], TYPE_SIGNATURE)
        self.assertEqual(possession["domain"], "identity")
        self.assertEqual(possession["payload"], artifact_cid(publication))
        self.assertEqual(possession["keyFingerprint"], publication["keyFingerprint"])
        self.assertEqual(
            verify_signature_artifact(possession, publication["publicKey"]),
            [],
        )

    def test_certificate_signed_binds_orchestrator_to_case(self) -> None:
        question = make_question("q", asked_by="t", asked_at="2026-02-01T00:00:00Z")
        pub, cert, cert_sig = make_certificate_signed(
            orchestrator_seed=ORCHESTRATOR_SEED,
            identity_seed=IDENTITY_SEED,
            case_manifest=artifact_cid(question),
            issued_at="2026-02-01T00:00:00Z",
        )
        for artifact in (pub, cert, cert_sig):
            validate_artifact(artifact)
        self.assertEqual(pub["type"], TYPE_KEY_PUBLICATION)
        self.assertEqual(pub["role"], "orchestrator")
        self.assertEqual(cert["type"], TYPE_CERTIFICATE)
        self.assertEqual(cert["subjectKey"], artifact_cid(pub))
        self.assertEqual(cert["caseManifest"], artifact_cid(question))
        self.assertNotEqual(pub["keyFingerprint"], cert_sig["keyFingerprint"])
        _, identity_public = keypair_from_seed(IDENTITY_SEED)
        self.assertEqual(
            verify_signature_artifact(cert_sig, identity_public), []
        )  # the identity key signed the certificate
        self.assertNotEqual(
            verify_signature_artifact(cert_sig, pub["publicKey"]), []
        )  # the orchestrator's own key did not

    def test_signed_tree_head_and_generic_signature(self) -> None:
        sth, sth_sig = make_signed_tree_head_signed(
            log_id="log",
            tree_size=3,
            root_hash=hashlib.sha256(b"root").digest(),
            seed=IDENTITY_SEED,
            published_at="2026-02-01T00:00:00Z",
        )
        validate_artifact(sth)
        validate_artifact(sth_sig)
        self.assertEqual(sth_sig["domain"], DOMAIN_LOG_STH)
        self.assertEqual(sth_sig["payload"], artifact_cid(sth))

        question = make_question("q", asked_by="t")
        verdict_sig = make_signature_signed(
            seed=IDENTITY_SEED, domain=DOMAIN_VERDICT, payload=artifact_cid(question)
        )
        validate_artifact(verdict_sig)
        self.assertEqual(verdict_sig["domain"], DOMAIN_VERDICT)

    def test_select_signatures_filters_on_domain_and_payload(self) -> None:
        question = make_question("q", asked_by="t")
        payload = artifact_cid(question)
        verdict_sig = make_signature_signed(seed=IDENTITY_SEED, domain=DOMAIN_VERDICT, payload=payload)
        sth_sig = make_signature_signed(
            seed=IDENTITY_SEED, domain=DOMAIN_LOG_STH, payload=payload,
            signed_at="2026-02-01T00:00:00Z",
        )
        self.assertEqual(select_signatures([verdict_sig, sth_sig], domain=DOMAIN_VERDICT, payload=payload), [verdict_sig])
        self.assertEqual(select_signatures([verdict_sig], domain=DOMAIN_VERDICT, payload=artifact_cid(make_question("other", asked_by="t"))), [])


class TestVerifySignatureArtifact(unittest.TestCase):
    def setUp(self) -> None:
        seed, pk = keygen()
        self.seed, self.pk = seed, pk
        question = make_question("q", asked_by="t")
        self.payload = artifact_cid(question)
        self.signature_artifact = make_signature_signed(seed=seed, domain=DOMAIN_VERDICT, payload=self.payload)

    def test_valid_signature_returns_no_problems(self) -> None:
        self.assertEqual(verify_signature_artifact(self.signature_artifact, self.pk), [])

    def test_tampered_payload_rejected(self) -> None:
        tampered = dict(self.signature_artifact)
        tampered["payload"] = artifact_cid(make_question("other q", asked_by="t"))
        problems = verify_signature_artifact(tampered, self.pk)
        self.assertEqual(len(problems), 1)
        self.assertIn("verification failed", problems[0])

    def test_wrong_key_rejected_with_fingerprint_mismatch(self) -> None:
        _, other_pk = keygen()
        problems = verify_signature_artifact(self.signature_artifact, other_pk)
        self.assertEqual(len(problems), 1)
        self.assertIn("does not match the candidate key", problems[0])

    def test_unknown_key_reported(self) -> None:
        problems = verify_signature_artifact(self.signature_artifact, None)
        self.assertEqual(len(problems), 1)
        self.assertIn("no published key", problems[0])

    def test_malformed_artifact_rejected(self) -> None:
        broken = dict(self.signature_artifact)
        broken["codecVersion"] = 2
        problems = verify_signature_artifact(broken, self.pk)
        self.assertEqual(len(problems), 1)
        self.assertIn("invalid artifact", problems[0])


if __name__ == "__main__":
    unittest.main()
