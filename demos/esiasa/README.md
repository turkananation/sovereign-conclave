# eSiasa release demo: one real policy question, machine-verified end to end

This directory is the M7 exit-criterion demo: one real eSiasa policy
question run through the full v0.2 machine pipeline and verifiable by an
external party from artifacts and published keys alone.

**The question:** *Should Siaya County shift feeder-road maintenance from
reactive pothole patching to route-backed performance contracts with
quarterly speed-index verification?*

**The pipeline that produced it:**

1. `feeder-road-performance-contract.ledger.json` — the frozen Evidence
   Ledger (7 entries, public demo inputs).
2. The M6 server orchestrator convened the `esiasa-civic-stress` profile
   (6 seats + Marshall, 7 personae) at
   `case-esiasa-civic-stress-20261021T073000Z` and ran one standing-voice
   deliberation round: 7 blind opening positions, distillation, consensus
   score 90 ≥ threshold, early verdict with no dissent (the durable
   advice is therefore the standing envelope:
   *"the conclave advises care before an irreversible step"* — the M6
   documented mechanical-verdict deviation; provider seats join under
   operator-side configuration).
3. `bundle/` — the materialized case bundle (54 artifacts), machine
   VERIFIED by `python3 -m conclave_core.verifier`.
4. `exports/` — the ADR decision record (`decision-record.md`), the
   JSON-LD record for the civic transparency portal
   (`decision-record.jsonld`), and the self-contained signed HTML
   transcript with the verification QR (`decision-record.html`).

## Verify it yourself (no trust in us required)

```bash
python3 -m conclave_core.verifier demos/esiasa/bundle --json
```

The public keys travel **inside** the bundle (`KeyPublication` and
`Certificate` artifacts), so an external party needs only the bundle
directory and the `cryptography>=45` dependency. `VERIFIED` on stderr and
exit code 0 mean: every artifact's canonical CBOR hash-chains to its CID,
the DAG closes, the verdict and every recorded signature verify against
the published keys, all RFC 6962 log heads verify, and the verdict is an
included log leaf.

The `exports/decision-record.html` QR encodes
`https://sovereign-conclave.org/verify/v0.2/<verdict-cid>`; that service
lands with the civic portal, so today the verification path above is the
complete contract.

## Regenerate it — verify the same record

The demo's identity/registry keystore seeds are committed under `keys/`
(**public by design** — anyone holding them can emit a bundle that this
demo's chain accepts; this is disclosed demo custody, not a
production claim). The generator writes them mode 0600 locally, but the
repository stores them plain text like any other committed file: treat
the demo keys as public. Regeneration reproduces the record: fixed seeds and a
fixed per-case orchestrator seed make every artifact except `Signature`
CID-identical, and ML-DSA signing is hedged (FIPS 204 §5.4), so each
regeneration carries fresh-but-equivalent signature bytes and therefore
fresh CIDs wherever signatures are linked. Every regeneration verifies
exactly like the archive:

```bash
python3 scripts/generate_esiasa_demo.py
python3 -m conclave_core.verifier demos/esiasa/bundle
rm -f demos/esiasa/store.sqlite3   # the generator's scratch database
```

`tests/test_esiasa_release.py` verifies the committed archive, pins the
non-signature record layer (question, ledger, panel, personae, turns,
telemetry) byte-for-byte across a fresh regeneration, and re-exports the
committed bundle to assert the committed `exports/` match exactly.

## What this demo does NOT claim

- The standing-voice record demonstrates the machine protocol and record
  integrity, not the quality of provider-sourced deliberation (D-4
  advice-only, provider runs are operator-side).
- Demo evidence entries (`E1`…`E7`) are synthetic public inputs.
- The verify endpoint URL is a civic-portal placeholder for v0.2.
