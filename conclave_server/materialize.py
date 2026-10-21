"""M6 materialization: a case's store subset becomes a verifier bundle.

The standalone verifier (``conclave_core.verifier``) accepts exactly the
artifact shape the emitter writes; this module gives a server-housed case
the same offline shape: the case's tracked artifact CIDs, their
``.raw`` payload files, and a ``bundle.json`` carrying the manifest CID,
expected identity/registry fingerprints, and the transparency-log section
rebuilt from the case log's stored leaves (growth STHs, consistency proofs,
inclusion proofs). Kill/resume clean-DAG acceptance lands here: a resumed
case materializes and verifies like one that never crashed.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from conclave_core.keystore import IDENTITY_SEED_FILE, REGISTRY_SEED_FILE, load_or_create_seed
from conclave_core.merkle import consistency_proof
from conclave_core.mldsa import public_fingerprint, public_key_bytes

from .store import ArtifactStore

BUNDLE_VERSION = 1


def _encode_nodes(nodes: list[bytes]) -> list[str]:
    return [base64.b64encode(node).decode("ascii") for node in nodes]


def _log_section(store: ArtifactStore, case_ref: str, sth_cids: list[str]) -> dict[str, Any]:
    """Rebuild the bundle log contract from the case log's stored rows."""

    leaves = store.leaves(case_ref)
    section: dict[str, Any] = {
        "leaves": [str(leaf) for leaf in leaves],
        "sthCids": list(sth_cids),
        "consistency": [],
        "inclusion": {},
    }
    leaf_bytes = [leaf.cid_bytes() for leaf in leaves]
    for size in range(2, len(leaves) + 1):
        section["consistency"].append(
            {
                "first": size - 1,
                "second": size,
                "path": _encode_nodes(consistency_proof(size - 1, leaf_bytes[:size])),
            }
        )
    for index, leaf in enumerate(leaves):
        section["inclusion"][str(leaf)] = {
            "index": index,
            "treeSize": len(leaves),
            "path": _encode_nodes(store.inclusion_proof(case_ref, index, len(leaves))),
        }
    return section


def materialize_case(store: ArtifactStore, keys_dir: Path, case_ref: str, out_dir: Path) -> Path:
    """Write the case bundle; returns the bundle directory."""

    row = store.session(case_ref)
    if row is None:
        raise ValueError(f"no persisted case: {case_ref}")
    state = json.loads(row["state"])
    artifact_cids: list[str] = state.get("artifacts", [])

    out_dir = Path(out_dir)
    artifacts_dir = out_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    if not artifact_cids:
        raise ValueError(f"case has no tracked artifacts to materialize: {case_ref}")
    for cid_str in artifact_cids:
        raw = store.raw(cid_str)
        if raw is None:
            raise ValueError(f"case artifact missing from the store: {cid_str}")
        (artifacts_dir / f"{cid_str}.cbor").write_bytes(raw)

    for name in state.get("payloads", []):
        if name.startswith("_"):
            continue  # server-private control payloads never materialize
        payload = store.payload(name)
        if payload is None:
            raise ValueError(f"case payload missing from the store: {name}")
        (artifacts_dir / name).write_bytes(payload)

    identity_seed = load_or_create_seed(Path(keys_dir) / IDENTITY_SEED_FILE)
    registry_seed = load_or_create_seed(Path(keys_dir) / REGISTRY_SEED_FILE)
    config = {
        "version": BUNDLE_VERSION,
        "manifestCid": str(state["manifestCid"]),
        "expectedIdentityFingerprint": public_fingerprint(public_key_bytes(identity_seed)),
        "expectedRegistryFingerprint": public_fingerprint(public_key_bytes(registry_seed)),
        "log": _log_section(store, case_ref, state.get("sthCids", [])),
    }
    (out_dir / "bundle.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return out_dir
