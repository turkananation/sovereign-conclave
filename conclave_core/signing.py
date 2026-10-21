"""Hash-then-sign conventions for the conclave artifact DAG.

Every signature in the conclave protocol is an ML-DSA-65 signature produced
by :mod:`conclave_core.mldsa` (OpenSSL-backed). Conventions:

- **Payload is a CID (hash-then-sign).** A Signature artifact never carries
  artifact bytes; it references the artifact CID it attests and carries the
  3309-byte ML-DSA signature over that CID's raw binary form.
- **Domain separation uses the FIPS 204 context string.** The signing
  context is ``conclave/<domain>/v1`` (e.g. ``conclave/verdict/v1``), so a
  signature for one role can never be replayed as another.
- **Keys are published as artifacts.** A KeyPublication artifact carries the
  1952-byte public key and its fingerprint (sha256 over a domain-tagged
  prefix plus the key bytes). Signature artifacts carry ``keyFingerprint``;
  the verifier binds fingerprints to public keys resolved from the store.
- **Certificate chain.** The session orchestrator key is certified per case:
  a Certificate artifact binds (orchestrator KeyPublication CID,
  DeliberationManifest CID) and the conclave identity key signs that
  Certificate CID (domain ``certify-orchestrator``).

Trust anchors: the verifier takes the *expected conclave identity fingerprint*
(published with the release) and optionally an expected persona-registry
fingerprint. Every other key (session orchestrator) follows from the
certificate chain inside the DAG.

Chain orchestration lives in :mod:`conclave_core.verifier`, which owns the
artifact store; this module exposes the per-artifact cryptographic
conventions and builders.
"""

from __future__ import annotations

from .artifacts import (
    ArtifactError,
    artifact_cid,
    make_certificate,
    make_key_publication,
    make_signature,
    make_signed_tree_head,
    validate_artifact,
)
from .cid import Cid
from .mldsa import keypair_from_seed, public_fingerprint, sign, verify

__all__ = [
    "DOMAIN_VERDICT",
    "DOMAIN_ROUND_ATTESTATION",
    "DOMAIN_CERTIFY_ORCHESTRATOR",
    "DOMAIN_PERSONA_MANIFEST",
    "DOMAIN_LOG_STH",
    "DOMAIN_APPEAL_SCREENING",
    "context_for",
    "signature_message",
    "sign_cid",
    "make_key_publication",
    "make_key_publication_signed",
    "make_certificate_signed",
    "make_signed_tree_head_signed",
    "make_signature",
    "make_signature_signed",
    "verify_signature_artifact",
    "select_signatures",
]

# Signing domains (short strings; they become FIPS 204 context strings).
DOMAIN_VERDICT = "verdict"
DOMAIN_ROUND_ATTESTATION = "round-attestation"
DOMAIN_CERTIFY_ORCHESTRATOR = "certify-orchestrator"
DOMAIN_PERSONA_MANIFEST = "persona-manifest"
DOMAIN_LOG_STH = "log-sth"
DOMAIN_DISSENT_FILING = "dissent-filing"
DOMAIN_APPEAL_PETITION = "appeal-petition"
DOMAIN_APPEAL_SCREENING = "appeal-screening"
DOMAIN_APPEAL_VERDICT = "appeal-verdict"
DOMAIN_ARBITER_RULING = "arbiter-ruling"


def context_for(domain: str) -> bytes:
    """FIPS 204 context string binding a signature to its purpose."""

    context = f"conclave/{domain}/v1".encode("ascii")
    if len(context) > 255:
        raise ValueError("domain produces an over-long FIPS context")
    return context


def signature_message(payload: Cid) -> bytes:
    """The exact signed message: the raw 36-byte binary CID."""

    return payload.cid_bytes()


def sign_cid(seed: bytes, domain: str, payload: Cid) -> bytes:
    """ML-DSA-65 signature over an artifact CID for a given domain."""

    return sign(seed, signature_message(payload), context=context_for(domain))


def make_key_publication_signed(*, seed: bytes, role: str, domain: str | None = None, published_at=None, note=None):
    """Publish a keypair as (KeyPublication, possession Signature).

    The optional Signature (``domain``, defaulting to the role name) signs
    the KeyPublication CID with the published key itself, proving possession
    of the seed that generated it.
    """

    seed_bytes, public_key = keypair_from_seed(seed)
    publication = make_key_publication(
        role=role, public_key=public_key, published_at=published_at, note=note
    )
    publication_cid = artifact_cid(publication)
    domain = domain or role
    signature_artifact = make_signature(
        domain=domain,
        key_fingerprint=publication["keyFingerprint"],
        payload=publication_cid,
        signature=sign_cid(seed_bytes, domain, publication_cid),
        signed_at=published_at,
        note=note,
    )
    return publication, signature_artifact


def make_certificate_signed(
    *, orchestrator_seed: bytes, identity_seed: bytes, case_manifest: Cid,
    issued_at=None, note=None,
):
    """Bind an ephemeral session-orchestrator key to one case.

    Returns ``(orchestrator_publication, certificate, signature)``:
    - ``orchestrator_publication``: KeyPublication (role ``orchestrator``),
    - ``certificate``: Certificate binding publication → case manifest,
    - ``signature``: identity-key Signature over the certificate CID
      (domain ``certify-orchestrator``).
    """

    _, orchestrator_public = keypair_from_seed(orchestrator_seed)
    publication = make_key_publication(
        role="orchestrator", public_key=orchestrator_public, published_at=issued_at, note=note
    )
    certificate = make_certificate(
        subject_key=artifact_cid(publication),
        case_manifest=case_manifest,
        issued_at=issued_at,
        note=note,
    )
    certificate_cid = artifact_cid(certificate)
    _, identity_public = keypair_from_seed(identity_seed)
    signature_artifact = make_signature(
        domain=DOMAIN_CERTIFY_ORCHESTRATOR,
        key_fingerprint=public_fingerprint(identity_public),
        payload=certificate_cid,
        signature=sign_cid(identity_seed, DOMAIN_CERTIFY_ORCHESTRATOR, certificate_cid),
        signed_at=issued_at,
        note=note,
    )
    return publication, certificate, signature_artifact


def make_signed_tree_head_signed(*, log_id: str, tree_size: int, root_hash: bytes, seed: bytes, published_at=None, note=None):
    """Sign a transparency-log checkpoint (SignedTreeHead artifact)."""

    _, public_key = keypair_from_seed(seed)
    sth = make_signed_tree_head(
        log_id=log_id, tree_size=tree_size, root_hash=root_hash, published_at=published_at, note=note
    )
    sth_cid = artifact_cid(sth)
    signature_artifact = make_signature(
        domain=DOMAIN_LOG_STH,
        key_fingerprint=public_fingerprint(public_key),
        payload=sth_cid,
        signature=sign_cid(seed, DOMAIN_LOG_STH, sth_cid),
        signed_at=published_at,
        note=note,
    )
    return sth, signature_artifact


def make_signature_signed(*, seed: bytes, domain: str, payload: Cid, signed_at=None, note=None):
    """Sign an arbitrary artifact CID with a seed under ``domain``.

    Returns ``(signature_artifact,)`` — the Signature artifact carrying the
    signature over ``payload``'s CID and the signer's fingerprint.
    """

    _, public_key = keypair_from_seed(seed)
    return make_signature(
        domain=domain,
        key_fingerprint=public_fingerprint(public_key),
        payload=payload,
        signature=sign_cid(seed, domain, payload),
        signed_at=signed_at,
        note=note,
    )


def verify_signature_artifact(signature_artifact: dict, public_key: bytes | None) -> list[str]:
    """Check a Signature artifact against a candidate public key.

    ``public_key`` is the 1952-byte ML-DSA-65 public key resolved for
    ``signature_artifact["keyFingerprint"]`` (None when unknown). Returns a
    list of problems; empty means the signature is valid for this key, its
    payload CID, and its domain context.
    """

    problems: list[str] = []
    try:
        validate_artifact(signature_artifact)
    except ArtifactError as exc:
        return [f"signature: invalid artifact: {exc}"]

    label = f"signature[{signature_artifact['domain']} {signature_artifact['payload']}]"
    if public_key is None:
        return [f"{label}: no published key for fingerprint "
                f"{signature_artifact['keyFingerprint'][:16]}…"]
    if public_fingerprint(public_key) != signature_artifact["keyFingerprint"]:
        return [f"{label}: fingerprint {signature_artifact['keyFingerprint'][:16]}… "
                "does not match the candidate key"]
    if not verify(
        public_key,
        signature_artifact["payload"].cid_bytes(),
        signature_artifact["signature"],
        context=context_for(signature_artifact["domain"]),
    ):
        problems.append(f"{label}: ML-DSA-65 verification failed")
    return problems


def select_signatures(signatures, *, domain: str, payload: Cid) -> list[dict]:
    """Signature artifacts matching a domain and exact payload CID."""

    return [
        signature_artifact for signature_artifact in signatures
        if signature_artifact.get("domain") == domain and signature_artifact.get("payload") == payload
    ]
