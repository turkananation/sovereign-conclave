"""Local key custody for the conclave command line.

The ML-DSA-65 private key is a 32-byte FIPS 204 seed (see
:mod:`conclave_core.mldsa`). This module only stores and reads those seeds;
all cryptography stays in the OpenSSL-backed library.

Layout under a keys directory:

- ``identity.seed``  the long-lived conclave identity key of this
  installation; its public fingerprint is the bundle's trust anchor,
- ``registry.seed``  the persona-registry key this installation uses to
  sign the personas it convenes.

Seeds are created with ``os.urandom`` on first use and written with owner
mode 0600. Custody rules are the operator's responsibility: these files
are the identity of the conclave — keep them out of the repository tree
and out of any eventual cloud sync.
"""

from __future__ import annotations

import os
from pathlib import Path

from .mldsa import SEED_SIZE

__all__ = ["IDENTITY_SEED_FILE", "REGISTRY_SEED_FILE", "load_or_create_seed", "keystore_paths"]

IDENTITY_SEED_FILE = "identity.seed"
REGISTRY_SEED_FILE = "registry.seed"


def load_or_create_seed(path: Path) -> bytes:
    """Read an existing ML-DSA seed, or mint one with ``os.urandom``."""

    path = path.expanduser()
    if path.exists():
        seed = path.read_bytes()
        if len(seed) != SEED_SIZE:
            raise RuntimeError(
                f"{path}: expected a {SEED_SIZE}-byte seed, found {len(seed)} bytes"
            )
        return seed
    path.parent.mkdir(parents=True, exist_ok=True)
    seed = os.urandom(SEED_SIZE)
    staging = path.with_name(path.name + ".creating")
    descriptor = os.open(
        staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_TRUNC, 0o600
    )
    try:
        os.write(descriptor, seed)
    finally:
        os.close(descriptor)
    os.replace(staging, path)
    return seed


def keystore_paths(keys_dir: Path) -> tuple[Path, Path]:
    return keys_dir / IDENTITY_SEED_FILE, keys_dir / REGISTRY_SEED_FILE
