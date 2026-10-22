"""Conclave verdict export (M7): publish one case's advised record.

Reads only a verifier-clean materialized bundle directory (bundle.json +
artifacts/*.cbor) and renders, deterministically from the stored artifact
bytes (artifact timestamps only; no wall-clock or host data):

- ``adr``      — an Architecture/Adjudication Decision Record markdown file.
- ``jsonld``   — a JSON-LD record for the civic transparency portal.
- ``html``     — a self-contained signed-record HTML transcript (verdict
  CID, dissents, evidence ledger, RFC 6962 verification block, and — when
  the optional ``qrcode`` extra is installed — a verification QR resolving
  to the configured verify endpoint).
- ``pdf``      — the same HTML rendered to PDF through WeasyPrint
  (documented optional extra; refused with install instructions when not
  installed).

An export of an unverifiable record would be a misuse of the record, so
the tool refuses bundles with verifier findings. The HTML/PDF are
"signed" in the protocol sense: the render carries the verdict CID, the
identity Signature over it, and the transparency-log head, so a reader
can check the artifacts against the bundle chain offline — byte-level
PAdES document signing remains out of scope for v0.2 (documented
deviation).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conclave_core.appeals import decode_store  # noqa: E402
from conclave_core.cid import Cid, parse  # noqa: E402
from conclave_core.verifier import verify_bundle  # noqa: E402

LOGGED_TYPES = ("Verdict", "Dissent", "EvidenceLedger", "Appeal", "AppealScreening",
                "AppealVerdict", "ArbiterRuling")

DEFAULT_VERIFY_ENDPOINT = "https://sovereign-conclave.org/verify/v0.2/"

_CID_SCHEME = "urn:conclave:cid:"


def cid_urn(cid: str | Cid) -> str:
    """Stable ``urn:conclave:cid:...`` identifier form for JSON-LD records."""

    return _CID_SCHEME + str(cid)


class ExportError(Exception):
    """The export cannot proceed (refusal or a missing optional extra)."""


# -- material ---------------------------------------------------------------


def load_case(bundle_dir: Path) -> tuple[dict, dict]:
    """Verify the bundle, then return ``(store, config)`` for rendering."""

    bundle_dir = Path(bundle_dir)
    problems, _summary = verify_bundle(bundle_dir)
    if problems:
        raise ExportError(
            "refusing to export a bundle that does not verify:\n"
            + "\n".join(f"- {problem}" for problem in problems)
        )
    return decode_store(bundle_dir), json.loads(
        (bundle_dir / "bundle.json").read_text(encoding="utf-8")
    )


def _resolve(store: dict[Cid, dict], cid, bundle_dir: Path) -> dict:
    artifact = store.get(cid) if isinstance(cid, Cid) else store.get(parse(cid))
    if artifact is None:
        raise ExportError(f"bundle {bundle_dir.name}: unresolvable link {cid}")
    return artifact


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _log_record(store: dict[Cid, dict], config: dict, bundle_dir: Path) -> dict:
    """Transparency-log summary: head + per-leaf inclusion paths."""

    log = config["log"]
    sth_cid = parse(log["sthCids"][-1])
    sth = _resolve(store, sth_cid, bundle_dir)
    head = {
        "sthCid": str(sth_cid),
        "treeSize": sth["treeSize"],
        "rootHash": _b64(sth["rootHash"]),
        "publishedAt": sth["publishedAt"],
        "logId": sth["logId"],
    }
    leaves = []
    for leaf in log["leaves"]:
        leaf_cid = parse(leaf)
        inclusion = log["inclusion"][leaf]
        leaves.append(
            {
                "cid": leaf,
                "index": inclusion["index"],
                "treeSize": inclusion["treeSize"],
                "path": inclusion["path"],
                "artifact": store.get(leaf_cid, {}),
            }
        )
    return {"head": head, "leaves": leaves}


# -- ADR markdown -------------------------------------------------------------


def render_adr(store: dict[Cid, dict], config: dict, bundle_dir: Path,
               verify_endpoint: str) -> str:
    bundle_dir = Path(bundle_dir)
    manifest = _resolve(store, parse(config["manifestCid"]), bundle_dir)
    case_id = manifest["caseId"]
    title = manifest.get("title") or case_id
    question = _resolve(store, manifest["question"], bundle_dir)
    verdict_cid = manifest.get("verdict")
    verdict = (
        _resolve(store, verdict_cid, bundle_dir)
        if verdict_cid is not None
        else None
    )
    ledger = _resolve(store, manifest["evidenceLedger"], bundle_dir)
    panel = _resolve(store, manifest["panel"], bundle_dir)
    record = _log_record(store, config, bundle_dir)

    lines: list[str] = []
    lines.append(f"# Conclave Decision Record — {title}")
    lines.append("")
    lines.append(f"- **Record ID:** `{case_id}`")
    lines.append("")
    lines.append("**Status: advised (non-binding).** The Sovereign Conclave produces")
    lines.append("a recommendation for the human owner; it records dissent explicitly and")
    lines.append("orders nobody to act.")
    lines.append("")

    if verdict is not None:
        lines.append("## Decision")
        lines.append("")
        lines.append(f"> {verdict['recommendation']}")
        lines.append("")
        lines.append(f"- **Confidence:** {verdict['confidence']}")
        if verdict.get("optionsRanked"):
            ranked = " > ".join(str(opt) for opt in verdict["optionsRanked"])
            lines.append(f"- **Options ranked:** {ranked}")
        if verdict.get("whatWouldChangeIt"):
            lines.append(f"- **What would change it:** {verdict['whatWouldChangeIt']}")
        if verdict.get("dissentRecordedNote"):
            lines.append(
                f"- **Dissent recorded note:** {verdict['dissentRecordedNote']}"
            )
        lines.append(f"- **Verdict CID:** `{cid_urn(verdict_cid)}`")
        lines.append(f"- **Issued:** {verdict['issuedAt']}")
        lines.append("")

        lines.append("### Recorded vote")
        lines.append("")
        if verdict["votes"]:
            lines.append("| Seat | Weight (micro-share) | Stance |")
            lines.append("| --- | --- | --- |")
            for vote in verdict["votes"]:
                lines.append(
                    f"| {vote['seatId']} | {vote['weightMicro']} | "
                    f"{str(vote['stance']).replace('|', '/')} |"
                )
            lines.append("")
        else:
            lines.append(
                "*Recorded without a voting panel (validated form only).*"
            )
            lines.append("")

    lines.append("## Question")
    lines.append("")
    lines.append(f"**{question['text']}**")
    lines.append("")
    if question.get("options"):
        lines.append(
            "Options presented: " + ", ".join(str(o) for o in question["options"])
        )
        lines.append("")
    lines.append(
        f"*Asked by {question['askedBy']} at {question['askedAt']}"
        f" — `{cid_urn(manifest['question'])}`.*"
    )
    lines.append("")

    lines.append("## Evidence ledger")
    lines.append("")
    lines.append("| ID | Item | Source (kind) | Handling | Sensitivity |")
    lines.append("| --- | --- | --- | --- | --- |")
    for entry in ledger["entries"]:
        provenance = entry.get("provenance", {})
        lines.append(
            f"| {entry['id']} | {entry['item'].replace('|', '/')} | "
            f"{provenance.get('source', '')} ({provenance.get('kind', '')}) | "
            f"{entry.get('handling', '')} | {entry.get('sensitivity', 'public')} |"
        )
    lines.append("")

    lines.append("## Deliberation record")
    lines.append("")
    lines.append(
        f"- **Panel:** {', '.join(seat_name(panel, seat, store) for seat in panel['seats'])}"
    )
    if panel.get("quorum"):
        lines.append(f"- **Quorum:** {panel['quorum']} seats")
    lines.append(f"- **Convened:** {panel['convenedAt']}")

    for round_cid in manifest.get("rounds", []):
        round_artifact = _resolve(store, round_cid, bundle_dir)
        lines.append("")
        kind = round_artifact.get("roundKind", "deliberation")
        lines.append(
            f"### Round {round_artifact['index']} ({kind})"
            f" — participants: {', '.join(round_artifact['participants'])}"
        )
        lines.append("")
        summary_cid = round_artifact.get("distilledSummary")
        if summary_cid is not None:
            summary = _resolve(store, summary_cid, bundle_dir)
            lines.append(f"Distilled record (model: {summary.get('modelId', 'unrecorded')}):")
            lines.append("")
            lines.append(f"> {summary['summaryText']}")
            if summary.get("openDisagreements"):
                disagreements = "; ".join(str(d) for d in summary["openDisagreements"])
                lines.append(f"- **Open disagreements:** {disagreements}")
            lines.append("")
            for position in summary["positions"]:
                cites = ", ".join(position.get("citations", [])) or "—"
                lines.append(
                    f"- **{position['seatId']}**: {position['stance']} (cites: {cites})"
                )
        elif round_artifact.get("noDistillationReason"):
            lines.append(
                f"*Distillation failed: {round_artifact['noDistillationReason']}; "
                "the historical verbatim record governs.*"
            )
            lines.append("")
        else:
            lines.append("*No distilled record (structural round).*")
            lines.append("")

    if verdict is not None and verdict.get("dissents"):
        lines.append("## Dissents")
        lines.append("")
        for dissent_cid in verdict["dissents"]:
            dissent = _resolve(store, dissent_cid, bundle_dir)
            cites = ", ".join(dissent["citedLedgerIds"]) or "—"
            lines.append(
                f"- **{dissent['seatId']}** (filed {dissent['filedAt']}, cites {cites}): "
                f"{dissent['grounds']} — `{cid_urn(dissent_cid)}`"
            )
        lines.append("")

    lines.append("## Transparency and verification")
    lines.append("")
    lines.append(f"- **Bundle:** `{bundle_dir.name}` "
                 f"(machine-verified before export; `python3 -m conclave_core.verifier`)")
    lines.append(
        f"- **Identity fingerprint:** `{config['expectedIdentityFingerprint']}`"
    )
    lines.append(
        f"- **Personas registry fingerprint:** `{config['expectedRegistryFingerprint']}`"
    )
    head = record["head"]
    lines.append(
        f"- **Log head:** size {head['treeSize']}, root `{head['rootHash']}`, "
        f"published {head['publishedAt']} — `{cid_urn(head['sthCid'])}`"
    )
    lines.append("")
    lines.append("| Log leaf | Artifact type | Inclusion (index of size) | Audit path (base64) |")
    lines.append("| --- | --- | --- | --- |")
    for leaf in record["leaves"]:
        artifact_type = leaf["artifact"].get("type", "?")
        lines.append(
            f"| `{cid_urn(leaf['cid'])}` | {artifact_type} | "
            f"{leaf['index']} of {leaf['treeSize']} | "
            f"{', '.join(leaf['path']) or '—'} |"
        )
    lines.append("")
    lines.append(f"- **Verify endpoint (QR target):** "
                 f"{verify_endpoint}{quote(str(verdict_cid or manifest_cid))}")
    lines.append("")
    lines.append("External verification: fetch the bundle directory and run the")
    lines.append("offline verifier — public keys travel inside the bundle as")
    lines.append("`KeyPublication` artifacts, so verification needs no trust in the")
    lines.append("host and no prior key exchange.")
    lines.append("")
    return "\n".join(lines)


def seat_name(panel: dict, seat, store: dict[Cid, dict]) -> str:
    """Render one convened seat as ``name (persona model)``."""

    entry = seat if isinstance(seat, dict) else {"seatId": str(seat)}
    persona = store.get(entry.get("persona"))  # optional resolution
    model = (
        f" {persona['model']}" if isinstance(persona, dict) and persona.get("model") else ""
    )
    return f"{entry.get('seatId', entry.get('id', str(seat)))} ({model.strip()})"


# -- JSON-LD ---------------------------------------------------------------


def render_jsonld(store: dict[Cid, dict], config: dict, bundle_dir: Path,
                  verify_endpoint: str) -> str:
    bundle_dir = Path(bundle_dir)
    manifest_cid = parse(config["manifestCid"])
    manifest = _resolve(store, manifest_cid, bundle_dir)
    case_id = manifest["caseId"]
    title = manifest.get("title") or case_id
    question = _resolve(store, manifest["question"], bundle_dir)
    ledger = _resolve(store, manifest["evidenceLedger"], bundle_dir)
    panel = _resolve(store, manifest["panel"], bundle_dir)
    verdict_cid = manifest.get("verdict")
    verdict = (
        _resolve(store, verdict_cid, bundle_dir) if verdict_cid is not None else None
    )
    record = _log_record(store, config, bundle_dir)

    node: dict = {
        "@context": [
            "https://schema.org",
            {
                "conclave": "https://sovereign-conclave.org/v0.2#",
                "cid": {"@id": "https://sovereign-conclave.org/v0.2#cid",
                        "@type": "@id"},
            },
        ],
        "@type": ["conclave:Decision", "https://schema.org/Conclusion"],
        "@id": cid_urn(manifest_cid),
        "name": title,
        "identifier": case_id,
        "conclave:status": "advised-non-binding",
        "conclave:question": {
            "@id": cid_urn(manifest["question"]),
            "text": question["text"],
            "askedBy": question["askedBy"],
            "askedAt": question["askedAt"],
        },
        "conclave:panel": {
            "@id": cid_urn(manifest["panel"]),
            "seats": [seat.get("seatId", seat.get("id", str(seat))) for seat in panel["seats"]],
            "convenedAt": panel["convenedAt"],
        },
        "conclave:evidence": [
            {
                "@id": cid_urn(f"E{index}=" + entry["id"]),
                "conclave:evidenceId": entry["id"],
                "description": entry["item"],
                "conclave:source": entry.get("provenance", {}).get("source", ""),
                "conclave:sourceKind": entry.get("provenance", {}).get("kind", ""),
                "conclave:handling": entry.get("handling", ""),
                "conclave:sensitivity": entry.get("sensitivity", "public"),
            }
            for index, entry in enumerate(ledger["entries"])
        ],
        "conclave:logHead": {
            "@id": cid_urn(record["head"]["sthCid"]),
            "treeSize": record["head"]["treeSize"],
            "rootHashBase64": record["head"]["rootHash"],
            "publishedAt": record["head"]["publishedAt"],
        },
        "conclave:logLeaves": [
            {
                "@id": cid_urn(leaf["cid"]),
                "artifactType": leaf["artifact"].get("type", "?"),
                "index": leaf["index"],
                "treeSize": leaf["treeSize"],
                "auditPathBase64": leaf["path"],
            }
            for leaf in record["leaves"]
        ],
        "conclave:verifyEndpoint": verify_endpoint,
    }

    if verdict is not None:
        node["conclave:verdict"] = {
            "@id": cid_urn(verdict_cid),
            "recommendation": verdict["recommendation"],
            "confidence": verdict["confidence"],
            "issuedAt": verdict["issuedAt"],
            "optionsRanked": [str(opt) for opt in verdict.get("optionsRanked", [])],
            "whatWouldChangeIt": verdict.get("whatWouldChangeIt"),
            "votes": [
                {
                    "seatId": vote["seatId"],
                    "weightMicro": vote["weightMicro"],
                    "stance": vote["stance"],
                }
                for vote in verdict["votes"]
            ],
        }
        node["conclave:dissents"] = [
            {
                "@id": cid_urn(dissent_cid),
                "seatId": dissent["seatId"],
                "grounds": dissent["grounds"],
                "citedLedgerIds": dissent["citedLedgerIds"],
                "filedAt": dissent["filedAt"],
            }
            for dissent_cid in (verdict.get("dissents") or [])
            for dissent in [_resolve(store, dissent_cid, bundle_dir)]
        ]

    # remaining lifecycle leaves (appeals, screenings, rulings) render as disputes
    disputes = []
    for leaf in record["leaves"]:
        artifact = leaf["artifact"]
        if artifact.get("type") in ("Appeal", "AppealScreening", "AppealVerdict",
                                    "ArbiterRuling"):
            disputes.append(
                {
                    "@id": cid_urn(leaf["cid"]),
                    "@type": f"conclave:{artifact['type']}",
                    "conclave:trigger": artifact.get("trigger"),
                    "conclave:grounds": artifact.get("grounds"),
                }
            )
    if disputes:
        node["conclave:disputes"] = disputes

    return json.dumps(node, indent=2, sort_keys=True) + "\n"


# -- HTML -----------------------------------------------------------------


def _esc(text) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_html(store: dict[Cid, dict], config: dict, bundle_dir: Path,
                verify_endpoint: str) -> str:
    bundle_dir = Path(bundle_dir)
    manifest = _resolve(store, parse(config["manifestCid"]), bundle_dir)
    case_id = manifest["caseId"]
    title = manifest.get("title") or case_id
    question = _resolve(store, manifest["question"], bundle_dir)
    ledger = _resolve(store, manifest["evidenceLedger"], bundle_dir)
    panel = _resolve(store, manifest["panel"], bundle_dir)
    verdict_cid = manifest.get("verdict")
    verdict = (
        _resolve(store, verdict_cid, bundle_dir) if verdict_cid is not None else None
    )
    record = _log_record(store, config, bundle_dir)

    target = quote(str(verdict_cid or manifest_cid))
    verify_url = verify_endpoint + target

    rows: list[str] = []
    rows.append(
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{_esc(title)} — Conclave record</title>"
        "<style>"
        "body{font-family:'Iowan Old Style',Georgia,serif;margin:0 auto;max-width:56rem;"
        "padding:2rem 1.5rem;color:#16161d;background:#fbfaf7;line-height:1.55}"
        "h1,h2,h3{font-family:'Avenir Next',Inter,system-ui,sans-serif;line-height:1.2}"
        "h1{font-size:1.9rem;margin:0 0 .2rem}h2{margin:2.2rem 0 .6rem;"
        "font-size:1.15rem;text-transform:uppercase;letter-spacing:.08em;"
        "color:#2c3563;border-bottom:1px solid #d8d4c8;padding-bottom:.25rem}"
        "header{border-bottom:3px double #2c3563;margin-bottom:1.2rem}"
        ".flag{display:inline-block;background:#2c3563;color:#fbfaf7;padding:.15rem .55rem;"
        "font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;border-radius:2px}"
        "blockquote{margin:0;padding:.6rem 1rem;border-left:3px solid #2c3563;"
        "background:#f1efe6;font-size:1.06rem}"
        "table{border-collapse:collapse;width:100%;font-size:.92rem;margin:.6rem 0}"
        "th,td{border:1px solid #d8d4c8;padding:.35rem .55rem;text-align:left;"
        "vertical-align:top}"
        "th{background:#f1efe6;font-family:system-ui,sans-serif;font-size:.8rem;"
        "text-transform:uppercase;letter-spacing:.06em}"
        "code{font-family:ui-monospace,'JetBrains Mono',monospace;font-size:.85rem;"
        "background:#f1efe6;padding:.08rem .3rem;border-radius:2px;word-break:break-all}"
        ".verify{background:#16161d;color:#eeead9;padding:1rem;border-radius:4px;"
        "font-size:.86rem;overflow-wrap:anywhere}"
        ".verify code{background:transparent;color:#9cc4ff}"
        ".foot{margin-top:2rem;font-size:.8rem;color:#6b6653;border-top:1px solid #d8d4c8;"
        "padding-top:.6rem}"
        ".qr{margin:.8rem 0}.qr svg{display:block}"
        "</style></head><body>"
    )
    rows.append(
        "<header><span class=\"flag\">Conclave advised record</span>"
        f"<h1>{_esc(title)}</h1><p><code>{_esc(case_id)}</code></p></header>"
    )
    rows.append(f"<p><strong>{_esc(question['text'])}</strong></p>")
    rows.append(
        f"<p><em>Asked by {_esc(question['askedBy'])} at {_esc(question['askedAt'])}"
        f" — published as a non-binding advisory record.</em></p>"
    )

    if verdict is not None:
        rows.append("<h2>Decision</h2>")
        rows.append(f"<blockquote>{_esc(verdict['recommendation'])}</blockquote>")
        rows.append(
            f"<p>Confidence: <strong>{_esc(verdict['confidence'])}</strong>"
            + (
                f" — options ranked: {_esc(' > '.join(str(o) for o in verdict['optionsRanked']))}"
                if verdict.get("optionsRanked")
                else ""
            )
            + (f" — what would change it: {_esc(verdict['whatWouldChangeIt'])}"
               if verdict.get("whatWouldChangeIt")
               else "")
            + "</p>"
        )
        rows.append(
            f"<p>Verdict CID: <code>{_esc(cid_urn(verdict_cid))}</code>"
            f"<br>Issued at {_esc(verdict['issuedAt'])}</p>"
        )
        rows.append(
            "<table><tr><th>Seat</th><th>Weight (micro-share)</th><th>Stance</th></tr>"
            + "".join(
                "<tr><td>" + _esc(vote["seatId"]) + "</td><td>"
                + str(vote["weightMicro"]) + "</td><td>" + _esc(vote["stance"]) + "</td></tr>"
                for vote in verdict["votes"]
            )
            + "</table>"
        )

    rows.append(
        "<h2>Evidence ledger</h2><table><tr><th>ID</th><th>Item</th>"
        "<th>Source (kind)</th><th>Handling</th><th>Sensitivity</th></tr>"
        + "".join(
            "<tr><td>" + _esc(entry["id"]) + "</td><td>" + _esc(entry["item"]) + "</td><td>"
            + _esc(entry.get("provenance", {}).get("source", ""))
            + " (" + _esc(entry.get("provenance", {}).get("kind", "")) + ")</td><td>"
            + _esc(entry.get("handling", "")) + "</td><td>"
            + _esc(entry.get("sensitivity", "public")) + "</td></tr>"
            for entry in ledger["entries"]
        )
        + "</table>"
    )

    rows.append(
        f"<h2>Panel</h2><p>{_esc(', '.join(seat_name(panel, seat, store) for seat in panel['seats']))}"
        f" — convened {_esc(panel['convenedAt'])}"
        + (f", quorum {_esc(panel['quorum'])}" if panel.get("quorum") else "")
        + ".</p>"
    )

    for round_cid in manifest.get("rounds", []):
        round_artifact = _resolve(store, round_cid, bundle_dir)
        rows.append(
            f"<h2>Round {_esc(round_artifact['index'])} — {_esc(round_artifact.get('roundKind', 'deliberation'))}</h2>"
            f"<p>Participants: {_esc(', '.join(round_artifact['participants']))}.</p>"
        )
        summary_cid = round_artifact.get("distilledSummary")
        if summary_cid is not None:
            summary = _resolve(store, summary_cid, bundle_dir)
            rows.append(f"<blockquote>{_esc(summary['summaryText'])}</blockquote>")
            rows.append(
                "<table><tr><th>Seat</th><th>Stance</th><th>Cites</th></tr>"
                + "".join(
                    "<tr><td>" + _esc(position["seatId"]) + "</td><td>"
                    + _esc(position["stance"]) + "</td><td>"
                    + _esc(", ".join(position.get("citations", [])) or "—") + "</td></tr>"
                    for position in summary["positions"]
                )
                + "</table>"
            )
            if summary.get("openDisagreements"):
                rows.append(
                    "<p>Open disagreements: "
                    + _esc("; ".join(str(d) for d in summary["openDisagreements"]))
                    + "</p>"
                )
        elif round_artifact.get("noDistillationReason"):
            rows.append(
                "<p><em>Distillation failed ("
                + _esc(round_artifact["noDistillationReason"])
                + "); the historical verbatim record governs.</em></p>"
            )
        else:
            rows.append("<p><em>No distilled record (structural round).</em></p>")

    if verdict is not None and verdict.get("dissents"):
        rows.append("<h2>Dissents</h2><ul>")
        for dissent_cid in verdict["dissents"]:
            dissent = _resolve(store, dissent_cid, bundle_dir)
            rows.append(
                f"<li><strong>{_esc(dissent['seatId'])}</strong> (filed "
                f"{_esc(dissent['filedAt'])}, cites "
                f"{_esc(', '.join(dissent['citedLedgerIds']) or '—')}): "
                f"{_esc(dissent['grounds'])}</li>"
            )
        rows.append("</ul>")

    head = record["head"]
    rows.append("<h2>Verification</h2><div class=\"verify\">")
    rows.append(f"bundle&nbsp;{_esc(bundle_dir.name)}")
    rows.append(
        f"<br>identity&nbsp;fingerprint&nbsp;<code>{_esc(config['expectedIdentityFingerprint'])}</code>"
    )
    rows.append(
        f"<br>registry&nbsp;fingerprint&nbsp;<code>{_esc(config['expectedRegistryFingerprint'])}</code>"
    )
    rows.append(
        f"<br>log&nbsp;head&nbsp;size&nbsp;{head['treeSize']} root&nbsp;<code>{_esc(head['rootHash'])}</code>"
        f" published&nbsp;{_esc(head['publishedAt'])}"
    )
    for leaf in record["leaves"]:
        rows.append(
            f"<br>leaf&nbsp;{leaf['index']}/{leaf['treeSize']}&nbsp;"
            f"{_esc(leaf['artifact'].get('type', '?'))}&nbsp;<code>{_esc(leaf['cid'])}</code>&nbsp;path&nbsp;"
            f"<code>{_esc(', '.join(leaf['path']))}</code>"
        )
    rows.append(
        "<br>offline&nbsp;verify:&nbsp;<code>python3 -m conclave_core.verifier "
        f"{_esc(bundle_dir.name)}</code>"
    )
    rows.append("</div>")
    if verdict is not None:
        rows.append(f"<p>Verify endpoint: <a href=\"{_esc(verify_url)}\">{_esc(verify_url)}</a></p>")

    qr = _qrcode_svg(verify_url)
    if qr is not None:
        rows.append(f"<div class=\"qr\">{qr}</div>")

    rows.append(
        "<p class=\"foot\">Rendered from a machine-verified artifact bundle of the"
        " Sovereign Conclave protocol (v0.2 codec). Advice only: this record"
        " recommends action to a human owner and orders nobody to act. Public"
        " keys travel inside the bundle; verification needs no trust in this"
        " document's host beyond receiving the bundle bytes.</p>"
    )
    rows.append("</body></html>\n")
    return "\n".join(rows)


def _qrcode_svg(content: str) -> str | None:
    """Verification QR (SVG) when the optional ``qrcode`` extra is installed."""

    try:
        import qrcode  # type: ignore[import-not-found]
        from qrcode.image.svg import SvgPathImage  # type: ignore[attr-defined]
    except ImportError:
        return None
    qr = qrcode.QRCode(border=2, image_factory=SvgPathImage)
    qr.add_data(content)
    qr.make()
    image = qr.make_image()
    try:
        data = image.to_string()
    except (AttributeError, TypeError):  # pragma: no cover - qrcode < 7
        buffer = io.StringIO()
        image.save(buffer)
        data = buffer.getvalue()
    return data.decode("utf-8") if isinstance(data, bytes) else data


# -- PDF (optional extra) ----------------------------------------------------


def render_pdf(html: str, bundle_dir: Path) -> bytes:
    try:
        from weasyprint import HTML  # type: ignore[import-not-found]
    except ImportError as error:
        raise ExportError(
            "the PDF export needs the documented optional WeasyPrint extra "
            "(system Pango/Harfbuzz required): pip install 'sovereign-conclave[pdf]' "
            "or pip install weasyprint; the HTML export is the stdlib baseline"
        ) from error
    return bytes(HTML(string=html, base_url=str(bundle_dir)).write_pdf())


# -- CLI -----------------------------------------------------------------


def export_all(
    bundle_dir: Path,
    out_dir: Path,
    formats: list[str],
    verify_endpoint: str,
) -> list[Path]:
    store, config = load_case(bundle_dir)
    rendered: dict[str, str] = {}
    if "adr" in formats:
        rendered["adr"] = render_adr(store, config, Path(bundle_dir), verify_endpoint)
    if "jsonld" in formats:
        rendered["jsonld"] = render_jsonld(store, config, Path(bundle_dir), verify_endpoint)
    html = None
    if "html" in formats or "pdf" in formats:
        html = render_html(store, config, Path(bundle_dir), verify_endpoint)
    if "html" in formats:
        rendered["html"] = html

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    titles = {
        "adr": "decision-record.md",
        "jsonld": "decision-record.jsonld",
        "html": "decision-record.html",
    }
    written: list[Path] = []
    for fmt, text in rendered.items():
        path = Path(out_dir) / titles[fmt]
        _write_atomic(path, text.encode("utf-8"))
        written.append(path)
    if "pdf" in formats:
        path = Path(out_dir) / "decision-record.pdf"
        _write_atomic(path, render_pdf(html, Path(bundle_dir)))
        written.append(path)
    return written


def _write_atomic(path: Path, data: bytes) -> None:
    staging = path.with_name("." + path.name + ".writing")
    staging.write_bytes(data)
    staging.replace(path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="verdict_export",
        description="Export a verifier-clean conclave case bundle as a civic "
        "decision record (ADR markdown, JSON-LD, signed HTML, optional PDF).",
        epilog="formats: adr, jsonld, html, pdf (comma list, repeatable not needed)",
    )
    parser.add_argument("bundle_dir", help="materialized case bundle directory")
    parser.add_argument("--out-dir", required=True, help="export destination directory")
    parser.add_argument(
        "--formats", default="adr,jsonld,html",
        help="comma-separated export formats (default: adr,jsonld,html)",
    )
    parser.add_argument(
        "--verify-endpoint", default=DEFAULT_VERIFY_ENDPOINT,
        help="base URL the verification QR/link resolves to (default: "
        f"{DEFAULT_VERIFY_ENDPOINT})",
    )
    args = parser.parse_args(argv)

    formats = [fmt.strip() for fmt in args.formats.split(",") if fmt.strip()]
    unknown = [fmt for fmt in formats if fmt not in ("adr", "jsonld", "html", "pdf")]
    if unknown:
        parser.error(f"unknown format(s): {', '.join(unknown)}")
    if not formats:
        parser.error("--formats is empty")
    if "pdf" in formats and "html" not in formats:
        formats.insert(formats.index("pdf"), "html")  # PDF renders from the same HTML

    try:
        written = export_all(
            Path(args.bundle_dir), Path(args.out_dir), formats, args.verify_endpoint
        )
    except ExportError as error:
        print(f"verdict_export: {error}", file=sys.stderr)
        return 2
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
