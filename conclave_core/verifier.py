"""Offline case verifier CLI for Sovereign Conclave (M2).

Verifies a deliberation case entirely offline — from canonical artifact
bytes plus published public keys alone, with no trust in the operator who
emitted the bundle. What it checks:

1. **Artifact integrity.** Every ``artifacts/<cid>.cbor`` in the bundle is
   re-canonicalized; if the decoded artifact's CID does not match its file
   name, the bundle is corrupt. Every artifact validates against its v0.2
   schema (codecVersion 1).
2. **DAG.** The case manifest and everything below it must pass
   ``conclave_core.artifacts.verify_manifest`` (every CID recomputed,
   rounds append-only, verdict linkage, retry/supersede semantics).
3. **Signatures.** All Signature artifacts must verify under the published
   key they claim, for their domain context, over their payload CID:
   - the Verdict is signed by the *identity* key (its fingerprint is pinned
     in ``bundle.json`` as the trust anchor),
   - the orchestrator key is certified per case: an identity-signed
     Certificate binds (orchestrator KeyPublication, this manifest),
   - every committed Round carries a valid round attestation by the
     certified orchestrator key,
   - every panel persona manifest carries a signature under a
     persona-registry key (optionally pinned),
   - every published key carries proof of possession (a verifying
     signature over the KeyPublication CID made by its own key).
4. **Transparency log.** RFC 6962 tree over leaf CIDs: leaves hash to the
   final STH root; successive tree heads carry valid consistency proofs;
   signed tree heads are identity-signed; every logged verdict has a valid
   inclusion proof.

Bundle layout:
    bundle/
      artifacts/<cid>.cbor     canonical DAG-CBOR bytes of every artifact
      bundle.json              case pointer + trust config + log section

Usage:
    python3 -m conclave_core.verifier <bundle-directory> [--json]

Exit code 0 = fully verified; 1 = problems found. Programmatic callers
should import :func:`verify_bundle`.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import sys
from pathlib import Path

from .artifacts import (
    ArtifactError,
    TYPE_CERTIFICATE,
    TYPE_DELIBERATION_MANIFEST,
    TYPE_KEY_PUBLICATION,
    TYPE_PANEL_MANIFEST,
    TYPE_PERSONA_MANIFEST,
    TYPE_ROUND,
    TYPE_SIGNED_TREE_HEAD,
    TYPE_SIGNATURE,
    TYPE_TURN,
    TYPE_VERDICT,
    artifact_cid,
    validate_artifact,
    verify_manifest,
)
from .cbor import decode
from .cid import Cid, CidError, parse
from .merkle import tree_hash, verify_consistency, verify_inclusion
from .signing import (
    DOMAIN_CERTIFY_ORCHESTRATOR,
    DOMAIN_LOG_STH,
    DOMAIN_PERSONA_MANIFEST,
    DOMAIN_ROUND_ATTESTATION,
    DOMAIN_VERDICT,
    verify_signature_artifact,
)

BUNDLE_VERSION = 1

__all__ = ["BUNDLE_VERSION", "load_bundle", "verify_bundle", "main"]


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------


def load_bundle(bundle_dir: Path) -> tuple[dict[Cid, dict], dict, list[str]]:
    """Load a case bundle. Returns ``(store, config, problems)``."""

    problems: list[str] = []
    bundle_dir = Path(bundle_dir)
    store: dict[Cid, dict] = {}

    config_path = bundle_dir / "bundle.json"
    if not config_path.is_file():
        return store, {}, [f"bundle: missing bundle.json under {bundle_dir}"]
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return store, {}, [f"bundle: unreadable bundle.json: {exc}"]
    if not isinstance(config, dict):
        return store, {}, ["bundle: bundle.json must be a JSON object"]
    if config.get("version") != BUNDLE_VERSION:
        return store, config, [f"bundle: unsupported bundle version {config.get('version')!r}"]

    artifact_dir = bundle_dir / "artifacts"
    if not artifact_dir.is_dir():
        return store, config, problems + ["bundle: missing artifacts/ directory"]

    for path in sorted(artifact_dir.glob("*.cbor")):
        label = f"artifact[{path.name}]"
        try:
            cid = parse(path.stem)
        except (CidError, ValueError) as exc:
            problems.append(f"{label}: unparseable CID file name: {exc}")
            continue
        raw = path.read_bytes()
        try:
            artifact = decode(raw)
        except Exception as exc:  # noqa: BLE001 - the loader must survive bad files
            problems.append(f"{label}: undecodable canonical CBOR: {exc}")
            continue
        if not isinstance(artifact, dict):
            problems.append(f"{label}: artifact is not a mapping")
            continue
        try:
            recomputed = artifact_cid(artifact)
            validate_artifact(artifact)
        except ArtifactError as exc:
            problems.append(f"{label}: schema invalid: {exc}")
            continue
        if recomputed != cid:
            problems.append(f"{label}: content hashes to {recomputed}, file claims {cid}")
            continue
        store[cid] = artifact

    return store, config, problems


def _collect(store: dict[Cid, dict], artifact_type: str) -> list[tuple[Cid, dict]]:
    return [(cid, artifact) for cid, artifact in store.items() if artifact.get("type") == artifact_type]


def _public_key_for(keys: dict[str, dict], fingerprint: str | None) -> bytes | None:
    entry = keys.get(fingerprint or "")
    return entry["publicKey"] if entry else None


# ---------------------------------------------------------------------------
# case signature chain
# ---------------------------------------------------------------------------


def _verify_case_signatures(
    store: dict[Cid, dict],
    manifest: dict,
    manifest_cid: Cid,
    expected_identity_fingerprint: str,
    expected_registry_fingerprint: str | None,
) -> list[str]:
    problems: list[str] = []

    publications = _collect(store, TYPE_KEY_PUBLICATION)
    keys: dict[str, dict] = {}
    for cid, publication in publications:
        try:
            validate_artifact(publication)
        except ArtifactError as exc:
            problems.append(f"key publication {cid}: invalid: {exc}")
            continue
        keys.setdefault(publication["keyFingerprint"], publication)

    signatures = _collect(store, TYPE_SIGNATURE)

    def verified_network(domain: str, payload: Cid) -> list[dict]:
        """Valid signatures for (domain, payload); side-effects problems."""

        results = []
        for _, signature_artifact in signatures:
            if signature_artifact.get("domain") != domain:
                continue
            if signature_artifact.get("payload") != payload:
                continue
            issues = verify_signature_artifact(
                signature_artifact, _public_key_for(keys, signature_artifact.get("keyFingerprint"))
            )
            problems.extend(issues)
            if not issues:
                results.append(signature_artifact)
        return results

    possession_by_publication: dict[Cid, list[dict]] = {}
    for cid, publication in publications:
        possession_by_publication[cid] = verified_network(publication["role"], cid)

    for cid, publication in publications:
        if not possession_by_publication[cid]:
            problems.append(
                f"key publication {cid}: no valid proof of possession over its own "
                "publication CID"
            )

    def key_role(fingerprint: str | None) -> str | None:
        entry = keys.get(fingerprint or "")
        return entry["role"] if entry else None

    # Certificates are issued while a case is open (they may bind to any
    # earlier version in the supersede chain), so build the chain id set.
    chain_ids: set[Cid] = {manifest_cid}
    supersedes_link = manifest.get("supersedes")
    while supersedes_link is not None and isinstance(supersedes_link, Cid):
        chain_ids.add(supersedes_link)
        prior_manifest = store.get(supersedes_link)
        supersedes_link = prior_manifest.get("supersedes") if isinstance(prior_manifest, dict) else None

    # — verdict signature, by the pinned identity key
    verdict_cid = manifest.get("verdict")
    if verdict_cid is not None:
        verdict_sigs = verified_network(DOMAIN_VERDICT, verdict_cid)
        if not verdict_sigs:
            problems.append(
                f"signature-chain: verdict {verdict_cid} has no valid identity signature"
            )
        for signature_artifact in verdict_sigs:
            fingerprint = signature_artifact["keyFingerprint"]
            if fingerprint != expected_identity_fingerprint:
                problems.append(
                    f"signature-chain: verdict signature from {fingerprint[:16]}… is not "
                    "the expected conclave identity key"
                )
            elif key_role(fingerprint) != "identity":
                problems.append(
                    "signature-chain: the expected identity fingerprint does not resolve "
                    "to an identity KeyPublication"
                )

    # — orchestrator certificate chain, bound to this case manifest
    orchestrator_fingerprints: set[str] = set()
    for _, signature_artifact in signatures:
        if signature_artifact.get("domain") != DOMAIN_CERTIFY_ORCHESTRATOR:
            continue
        cert_cid = signature_artifact.get("payload")
        certificate = store.get(cert_cid)
        if certificate is None or certificate.get("type") != TYPE_CERTIFICATE:
            problems.append(
                f"signature-chain: orchestrator certification {cert_cid} does not "
                "resolve to a Certificate"
            )
            continue
        if certificate.get("caseManifest") not in chain_ids:
            continue  # a certification for a different case; not part of this chain
        issues = verify_signature_artifact(
            signature_artifact, _public_key_for(keys, signature_artifact.get("keyFingerprint"))
        )
        problems.extend(issues)
        if issues:
            continue
        if signature_artifact["keyFingerprint"] != expected_identity_fingerprint:
            problems.append(
                f"signature-chain: orchestrator certificate {cert_cid} is not signed by "
                "the expected identity key"
            )
            continue
        subject_publication = store.get(certificate.get("subjectKey"))
        if (
            subject_publication is None
            or subject_publication.get("type") != TYPE_KEY_PUBLICATION
            or subject_publication.get("role") != "orchestrator"
        ):
            problems.append(
                f"signature-chain: certificate {cert_cid} subject does not resolve to "
                "an orchestrator KeyPublication"
            )
            continue
        orchestrator_fingerprints.add(subject_publication["keyFingerprint"])
    if not orchestrator_fingerprints:
        problems.append(
            f"signature-chain: no orchestrator certificate binds a session key to case "
            f"manifest {manifest_cid}"
        )

    # — round attestations by a certified orchestrator key
    for position, round_cid in enumerate(manifest.get("rounds", [])):
        round_artifact = store.get(round_cid)
        if round_artifact is None or round_artifact.get("type") != TYPE_ROUND:
            continue  # missing/corrupt rounds surfaced by verify_manifest
        if round_artifact.get("status") != "committed":
            continue  # aborted rounds need no attestation
        attestations = verified_network(DOMAIN_ROUND_ATTESTATION, round_cid)
        if not attestations:
            problems.append(
                f"signature-chain: round {position} {round_cid} has no valid "
                "orchestrator round attestation"
            )
            continue
        signers = {signature_artifact["keyFingerprint"] for signature_artifact in attestations}
        outsiders = signers - orchestrator_fingerprints
        if outsiders:
            problems.append(
                f"signature-chain: round {position} attested outside the certified "
                f"orchestrator set: {sorted(f[:16] + '…' for f in outsiders)}"
            )

    # — persona manifest signatures under a persona-registry key
    panel = store.get(manifest.get("panel"))
    persona_cids: list[Cid] = []
    if isinstance(panel, dict) and panel.get("type") == TYPE_PANEL_MANIFEST:
        for seat in panel.get("seats", []):
            if not isinstance(seat, dict) or not isinstance(seat.get("persona"), Cid):
                problems.append(
                    f"signature-chain: panel seat {seat.get('seatId') if isinstance(seat, dict) else seat} "
                    "does not carry a persona link"
                )
                continue
            persona_cids.append(seat["persona"])
    for position, round_cid in enumerate(manifest.get("rounds", [])):
        round_artifact = store.get(round_cid)
        if round_artifact is None or round_artifact.get("type") != TYPE_ROUND:
            continue  # missing/corrupt rounds surfaced by verify_manifest
        for turn_cid in round_artifact.get("turns", []) or []:
            turn_artifact = store.get(turn_cid)
            if (
                isinstance(turn_artifact, dict)
                and turn_artifact.get("type") == TYPE_TURN
                and isinstance(turn_artifact.get("persona"), Cid)
            ):
                persona_cids.append(turn_artifact["persona"])
    for persona_cid in dict.fromkeys(persona_cids):
        persona = store.get(persona_cid)
        if persona is None or persona.get("type") != TYPE_PERSONA_MANIFEST:
            problems.append(
                f"signature-chain: persona {persona_cid} does not resolve to a "
                "PersonaManifest artifact in the bundle"
            )
            continue
        registry_sigs = verified_network(DOMAIN_PERSONA_MANIFEST, persona_cid)
        if not registry_sigs:
            problems.append(
                f"signature-chain: persona {persona_cid} has no valid persona-registry "
                "signature"
            )
            continue
        signer_roles = {key_role(signature_artifact["keyFingerprint"]) for signature_artifact in registry_sigs}
        if signer_roles != {"persona-registry"}:
            problems.append(
                f"signature-chain: persona {persona_cid} signed by key(s) whose roles "
                f"are {sorted(str(r) for r in signer_roles)}"
            )
        if expected_registry_fingerprint is not None and not any(
            signature_artifact["keyFingerprint"] == expected_registry_fingerprint
            for signature_artifact in registry_sigs
        ):
            problems.append(
                f"signature-chain: persona {persona_cid} is not signed by the expected "
                "persona-registry key"
            )

    return problems


# ---------------------------------------------------------------------------
# transparency log
# ---------------------------------------------------------------------------


def _decode_nodes(value) -> list[bytes] | None:
    try:
        return [base64.b64decode(node) for node in value]
    except (TypeError, ValueError, binascii.Error):
        return None


def _verify_log(store: dict[Cid, dict], config: dict, expected_identity_fingerprint: str | None) -> list[str]:
    problems: list[str] = []
    log_config = config.get("log")
    if not isinstance(log_config, dict):
        return ["log: bundle.json carries no log section"]
    leaves_config = log_config.get("leaves")
    sth_cids = log_config.get("sthCids")
    if not isinstance(leaves_config, list) or not isinstance(sth_cids, list):
        return ["log: log section needs leaves (list) and sthCids (list)"]

    leaves: list[Cid] = []
    for position, entry in enumerate(leaves_config):
        try:
            leaves.append(parse(entry))
        except (CidError, ValueError, TypeError) as exc:
            problems.append(f"log: leaf[{position}] is not a CID: {exc}")
    if problems:
        return problems

    keys: dict[str, dict] = {}
    for _, publication in _collect(store, TYPE_KEY_PUBLICATION):
        if "keyFingerprint" in publication:
            keys[publication["keyFingerprint"]] = publication
    log_signatures = [
        (cid, signature_artifact)
        for cid, signature_artifact in _collect(store, TYPE_SIGNATURE)
        if signature_artifact.get("domain") == DOMAIN_LOG_STH
    ]

    # Every logged leaf that resolves to a Verdict artifact must carry a valid
    # identity verdict signature; the log cannot be used to launder an
    # unsigned or foreign-key verdict into the transparency log.
    if expected_identity_fingerprint is not None:
        all_signatures = _collect(store, TYPE_SIGNATURE)
        for leaf in leaves:
            resolved = store.get(leaf)
            if resolved is None or resolved.get("type") != TYPE_VERDICT:
                continue
            anchored = [
                signature_artifact for _, signature_artifact in all_signatures
                if signature_artifact.get("domain") == DOMAIN_VERDICT
                and signature_artifact.get("payload") == leaf
                and signature_artifact.get("keyFingerprint") == expected_identity_fingerprint
                and verify_signature_artifact(
                    signature_artifact,
                    _public_key_for(keys, signature_artifact.get("keyFingerprint")),
                ) == []
            ]
            if not anchored:
                problems.append(
                    f"log: logged verdict {leaf} is not signed by the expected identity key"
                )

    heads: list[dict] = []
    for sth_cid_str in sth_cids:
        try:
            sth_cid = parse(sth_cid_str)
        except (CidError, ValueError, TypeError) as exc:
            problems.append(f"log: sthCids entry {sth_cid_str} is not a CID: {exc}")
            continue
        sth = store.get(sth_cid)
        if sth is None or sth.get("type") != TYPE_SIGNED_TREE_HEAD:
            problems.append(f"log: signed tree head {sth_cid_str} not found in bundle")
            continue
        heads.append({**sth, "cid": sth_cid})
    heads.sort(key=lambda sth: sth.get("treeSize", -1))

    for sth in heads:
        sth_cid_str = str(sth["cid"])
        matching = [
            signature_artifact for _, signature_artifact in log_signatures
            if signature_artifact.get("payload") == sth["cid"]
        ]
        if not matching:
            problems.append(f"log: signed tree head {sth_cid_str} carries no log-sth signature")
        for signature_artifact in matching:
            problems.extend(
                verify_signature_artifact(
                    signature_artifact, _public_key_for(keys, signature_artifact.get("keyFingerprint"))
                )
            )
            if (
                expected_identity_fingerprint is not None
                and signature_artifact["keyFingerprint"] != expected_identity_fingerprint
            ):
                problems.append(
                    f"log: signed tree head {sth_cid_str} must be signed by the expected "
                    "conclave identity key"
                )

    if not heads:
        return problems + ["log: no signed tree heads resolved"]

    final = heads[-1]
    for sth in heads[:-1]:
        if sth.get("treeSize") == final.get("treeSize") and sth["cid"] != final["cid"]:
            problems.append(f"log: duplicate tree head at treeSize {sth.get('treeSize')}")
    if final.get("treeSize") != len(leaves):
        problems.append(
            f"log: final tree head {final['cid']} has treeSize {final.get('treeSize')} "
            f"but the bundle carries {len(leaves)} leaves"
        )
    else:
        computed_root = tree_hash([leaf.cid_bytes() for leaf in leaves])
        if computed_root != bytes(final["rootHash"]):
            problems.append(
                "log: leaves hash to "
                f"{computed_root.hex()[:16]}… but the final tree head claims "
                f"{bytes(final['rootHash']).hex()[:16]}…"
            )

    consistency_config = log_config.get("consistency") or []
    heads_by_size = {sth.get("treeSize"): sth for sth in heads}
    for entry in consistency_config:
        path = _decode_nodes(entry.get("path") if isinstance(entry, dict) else None)
        try:
            m = int(entry["first"])
            n = int(entry["second"])
        except (KeyError, TypeError, ValueError):
            problems.append(f"log: malformed consistency entry {entry!r}")
            continue
        if path is None or m not in heads_by_size or n not in heads_by_size:
            problems.append(
                f"log: consistency {m}->{n} lacks a usable path or matching tree heads"
            )
            continue
        old_root = bytes(heads_by_size[m]["rootHash"])
        new_root = bytes(heads_by_size[n]["rootHash"])
        if not verify_consistency(m, n, path, old_root, new_root):
            problems.append(f"log: consistency proof {m}->{n} does not verify")

    inclusion_config = log_config.get("inclusion") or {}
    for leaf_cid_str, proof_config in inclusion_config.items():
        try:
            leaf_cid = parse(leaf_cid_str)
        except (CidError, ValueError, TypeError) as exc:
            problems.append(f"log: inclusion key {leaf_cid_str} is not a CID: {exc}")
            continue
        if leaf_cid not in leaves:
            problems.append(f"log: inclusion subject {leaf_cid_str} is not a logged leaf")
            continue
        path = _decode_nodes(proof_config.get("path") if isinstance(proof_config, dict) else None)
        try:
            index = int(proof_config["index"])
            tree_size = int(proof_config["treeSize"])
        except (KeyError, TypeError, ValueError):
            problems.append(f"log: malformed inclusion entry for {leaf_cid_str}")
            continue
        sth = heads_by_size.get(tree_size)
        if sth is None or path is None:
            problems.append(
                f"log: inclusion proof for {leaf_cid_str} lacks a usable path or a tree "
                f"head at size {tree_size}"
            )
            continue
        if not verify_inclusion(leaf_cid.cid_bytes(), index, path, tree_size, bytes(sth["rootHash"])):
            problems.append(f"log: inclusion proof for {leaf_cid_str} does not verify")

    return problems


# ---------------------------------------------------------------------------
# top-level verification
# ---------------------------------------------------------------------------


def verify_bundle(bundle_dir: Path) -> tuple[list[str], dict]:
    """Fully verify a case bundle. Returns ``(problems, summary)``.

    An empty problem list means the bundle verified end to end.
    """

    store, config, problems = load_bundle(bundle_dir)
    counts: dict[str, int] = {}
    for artifact in store.values():
        artifact_type = artifact.get("type", "?")
        counts[artifact_type] = counts.get(artifact_type, 0) + 1
    summary: dict = {"artifacts": len(store), "artifactCounts": counts}

    if not config:
        summary["problems"] = problems
        return problems, summary

    def resolver(cid: Cid):
        return store.get(cid)

    expected_identity = config.get("expectedIdentityFingerprint")
    if expected_identity is not None and not isinstance(expected_identity, str):
        problems.append("case: expectedIdentityFingerprint must be a string")

    manifest_cid = None
    try:
        manifest_cid = parse(config.get("manifestCid"))
    except (CidError, ValueError, TypeError):
        pass
    manifest = store.get(manifest_cid) if manifest_cid is not None else None
    if manifest is None or manifest.get("type") != TYPE_DELIBERATION_MANIFEST:
        problems.append(
            f"case: manifestCid {config.get('manifestCid')!r} does not resolve to a "
            "DeliberationManifest in the bundle"
        )
    else:
        problems.extend(verify_manifest(manifest, resolver))
        problems.extend(
            _verify_case_signatures(
                store,
                manifest,
                manifest_cid,
                expected_identity,
                config.get("expectedRegistryFingerprint"),
            )
        )
        verdict_cid = manifest.get("verdict")
        if verdict_cid is not None:
            logged = (config.get("log") or {}).get("leaves") or []
            if str(verdict_cid) not in logged:
                problems.append(
                    f"case: verdict {verdict_cid} is not published in the bundle's "
                    "transparency-log leaves"
                )
    problems.extend(_verify_log(store, config, expected_identity))

    summary["problems"] = problems
    if not problems:
        summary["status"] = "VERIFIED"
    return problems, summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="conclave_core.verifier",
        description="Offline verification of a Sovereign Conclave case bundle.",
    )
    parser.add_argument("bundle", help="directory containing bundle.json + artifacts/")
    parser.add_argument("--json", action="store_true", help="emit a JSON summary")
    arguments = parser.parse_args(argv)

    problems, summary = verify_bundle(Path(arguments.bundle))
    if arguments.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    elif problems:
        print("FAILED to verify case bundle:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    else:
        print("VERIFIED:")
        print(f"  artifacts: {summary['artifacts']}")
        for artifact_type, count in sorted(summary.get("artifactCounts", {}).items()):
            print(f"    {artifact_type}: {count}")
        return 0
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
