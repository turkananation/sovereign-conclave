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
import threading
from pathlib import Path

from .mldsa import SEED_SIZE

__all__ = ["IDENTITY_SEED_FILE", "REGISTRY_SEED_FILE", "load_or_create_seed", "keystore_paths"]

IDENTITY_SEED_FILE = "identity.seed"
REGISTRY_SEED_FILE = "registry.seed"


def load_or_create_seed(path: Path) -> bytes:
    """Read an existing ML-DSA seed, or mint one with ``os.urandom``.

    Race-safe for concurrent first creation: whoever's staging file loses
    the O_EXCL race re-reads the winning file, so every concurrent caller
    ends up holding the same seed bytes.
    """

    path = path.expanduser()
    if path.exists():
        return _read_seed(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    while not path.exists():
        seed = os.urandom(SEED_SIZE)
        # staging names are unique to this writer so concurrent first
        # creation never collides; the final os.replace decides the winner
        staging = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.creating")
        descriptor = os.open(
            staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_TRUNC, 0o600
        )
        try:
            os.write(descriptor, seed)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(staging, path)
    return _read_seed(path)


def _read_seed(path: Path) -> bytes:
    seed = path.read_bytes()
    if len(seed) != SEED_SIZE:
        raise RuntimeError(
            f"{path}: expected a {SEED_SIZE}-byte seed, found {len(seed)} bytes"
        )
    return seed


def keystore_paths(keys_dir: Path) -> tuple[Path, Path]:
    return keys_dir / IDENTITY_SEED_FILE, keys_dir / REGISTRY_SEED_FILE
