# Verifying a Conclave record as an external party

This document is for people who did not run the deliberation and do not
trust the operator. It describes how to verify a Sovereign Conclave case
bundle (the `bundle/` directory format, `bundle.json` version 1) from the
artifacts and the public keys inside it — nothing else.

## What you need

- Python 3.11+ and the single dependency: `cryptography>=45`.
- The bundle directory handed to you (any channel; integrity is checked
  inside the bundle, not by its transport).
- Optionally: the operator's published identity fingerprint, compared to
  the value `bundle.json` names as `expectedIdentityFingerprint` (this is
  the step that turns "internally consistent" into "the conclave you meant").

## Run the offline verifier

```bash
python3 -m conclave_core.verifier <bundle-directory> [--json]
```

Exit code `0` and `status: VERIFIED` mean all of the following, checked
mechanically by the code under `conclave_core/verifier.py`:

1. **Artifact integrity** — every `artifacts/*.cbor` file decodes as
   canonical DAG-CBOR and hashes to the CID in its filename.
2. **DAG closure** — every artifact link resolves inside the bundle; the
   manifest chain closes (each manifest supersedes the previous one) and
   the verdict chains to the (non-superseded) final manifest.
3. **Signature chain** — the verdict is signed by the conclave identity
   key under the verdict domain; the per-case orchestrator key is
   certificate-bound to the identity key; round attestations and
   persona-registry signatures verify; key possession proofs match the
   published keys. The ML-DSA keys follow FIPS 204 seed mode: a 32-byte
   seed determines the key pair; signatures are hedged (§5.4), so the same
   logical record re-generated produces fresh signature bytes — bundles
   verify, they do not need to be byte-reproducible.
4. **Transparency log** — every `SignedTreeHead` is identity-signed; the
   RFC 6962 tree heads' roots match the recomputed Merkle tree of the
   leaves; consistency proofs bind each earlier head to the final head;
   the verdict is an included leaf with the stated audit path.
5. **Persona resolution** — each convened seat's persona manifest resolves
   and the registry signature covers the convened personas.

## What verification proves (and does not)

- It proves the record exists, is internally consistent, was signed by
  one long-lived conclave key, and its verdict and lifecycle documents
  are committed to a transparency log that cannot be pared back without
  breaking the containment proofs.
- It does not prove the operator's process — evidence quality and
  provider seats are the operator's custody; the record keeps those
  claims auditable via the evidence ledger and telemetry, not verified.
- Advice only: a verified verdict is still a recommendation to a human
  owner (D-4), not an action order.

## Verify a specific export

The civic decision record exports carry:

- the **verdict CID** (`bafy…`) you can locate in the verification
  section and in `artifacts/`;
- the **log head** (size, base64 root, published-at) as a file you can
  recheck under the same tree;
- the verdict leaf's **base64 audit path** — to recheck the inclusion
  claim outside the verifier, run:

```python
from conclave_core.cid import parse
from conclave_core.merkle import verify_inclusion
leaf = parse("<verdict-cid>")
audit = [base64.b64decode(p) for p in ["<path>"]]
root = base64.b64decode("<root-from-the-record>")
assert verify_inclusion(leaf.cid_bytes(), "<index>", audit, "<tree-size>", root)
```

- the **QR** in the HTML export (when the optional `qrcode` extra was
  installed at export time) encodes
  `https://sovereign-conclave.org/verify/v0.2/<verdict-cid>` — the civic
  portal endpoint lands post-v0.2; for now the bundle path above is the
  complete verification contract.

## The release demo

`demos/esiasa/` ships one real eSiasa policy question through the full
v0.2 machine pipeline, machine-verified at release time, with the layout
described in its README. Start there if you want a worked example.

## Reporting a discrepancy

Open an issue with the bundle directory name (`bundle.json`'s
`manifestCid`), the verifier's `--json` problem list, and (only if it is
not sensitive) the artifact file that failed. Do not paste private
material from restricted ledger entries; the relevant row hashes are in
the bundle already.
