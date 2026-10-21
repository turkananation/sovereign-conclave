"""ML-DSA-65 (FIPS 204) signing and verification for the conclave stack.

This module is a thin, honest adapter over the `cryptography` package
(``cryptography>=45``, which is backed by OpenSSL >= 3.5). OpenSSL's
ML-DSA-65 implementation does all of the actual cryptography — this module
implements none of it. It exists to:

- pin the parameter set (ML-DSA-65, category 3) and byte sizes in one place,
- define the conclave canonical message/context conventions,
- offer seed-based deterministic keypairs (FIPS 204 seed mode): a 32-byte
  seed fully determines the key pair, which keeps demos and CI reproducible,
- keep the rest of ``conclave_core`` importable without this dependency.

Sizes (ML-DSA-65): public key 1952 bytes, signatures 3309 bytes,
private seed 32 bytes (FIPS 204 seed mode; expanded keys stay inside the
OpenSSL-backed library).

Security: the primitive itself is upstream-vetted (OpenSSL). Custody of the
32-byte seed still matters: in production the seed belongs in a secret store;
the long-lived conclave identity key should be held in KMS/HSM tooling, not
in this repository.
"""

from __future__ import annotations

import hashlib
import os

ALGORITHM = "ML-DSA-65"

PK_SIZE = 1952    # ML-DSA-65 public key
SIG_SIZE = 3309   # ML-DSA-65 signature
SEED_SIZE = 32    # private key seed (FIPS 204 seed mode)

DEFAULT_CONTEXT = b"conclave/v1"

__all__ = [
    "ALGORITHM", "PK_SIZE", "SIG_SIZE", "SEED_SIZE", "DEFAULT_CONTEXT",
    "MldsaUnavailable", "backend_version", "keygen", "keypair_from_seed",
    "public_key_bytes", "public_fingerprint", "sign", "verify",
]


class MldsaUnavailable(RuntimeError):
    """Raised when the OpenSSL-backed ML-DSA backend cannot be loaded."""


def _backend():
    try:
        import cryptography
        from cryptography.hazmat.primitives.asymmetric import mldsa
    except ImportError as exc:  # pragma: no cover - exercised by CLI users
        raise MldsaUnavailable(
            "ML-DSA-65 requires the 'cryptography' package (OpenSSL 3.5-backed): "
            "pip install 'cryptography>=45'"
        ) from exc
    version = tuple(int(p) for p in cryptography.__version__.split(".")[:2])
    if version < (45, 0):
        raise MldsaUnavailable(
            f"ML-DSA support needs cryptography>=45, found {cryptography.__version__}"
        )
    return mldsa


def backend_version() -> str:
    import cryptography

    return cryptography.__version__


def keypair_from_seed(seed: bytes) -> tuple[bytes, bytes]:
    """Deterministic ML-DSA-65 keypair from a 32-byte seed.

    Returns ``(seed, public_key_bytes)``; the seed IS the private key
    (FIPS 204 seed mode), the public key is its 1952-byte encoding.
    """

    mldsa = _backend()
    if len(seed) != SEED_SIZE:
        raise ValueError(f"seed must be {SEED_SIZE} bytes, got {len(seed)}")
    private = mldsa.MLDSA65PrivateKey.from_seed_bytes(seed)
    return seed, private.public_key().public_bytes_raw()


def keygen() -> tuple[bytes, bytes]:
    """Fresh random keypair: returns ``(seed, public_key_bytes)``."""

    return keypair_from_seed(os.urandom(SEED_SIZE))


def public_key_bytes(seed: bytes) -> bytes:
    return keypair_from_seed(seed)[1]


def public_fingerprint(public_key: bytes) -> str:
    """Long-form fingerprint used to bind signatures to a published key."""

    if len(public_key) != PK_SIZE:
        raise ValueError(f"expected {PK_SIZE}-byte public key, got {len(public_key)}")
    return hashlib.sha256(b"conclave-id\0" + public_key).hexdigest()


def sign(
    private_key: bytes,
    message: bytes,
    context: bytes = DEFAULT_CONTEXT,
) -> bytes:
    """Sign ``message`` with a 32-byte private seed (hash-then-sign friendly).

    ``context`` is the FIPS 204 context string; conclave uses it for domain
    separation (e.g. ``b"conclave/verdict/v1"``) and verification MUST pass
    the same context or reject.
    """

    mldsa = _backend()
    return mldsa.MLDSA65PrivateKey.from_seed_bytes(private_key).sign(
        message, context=context or None
    )


def verify(
    public_key: bytes,
    message: bytes,
    signature: bytes,
    context: bytes = DEFAULT_CONTEXT,
) -> bool:
    """Verify an ML-DSA-65 signature; malformed inputs verify False."""

    mldsa = _backend()
    if len(public_key) != PK_SIZE:
        return False
    public = mldsa.MLDSA65PublicKey.from_public_bytes(public_key)
    try:
        public.verify(signature, message, context=context or None)
        return True
    except Exception:
        return False
