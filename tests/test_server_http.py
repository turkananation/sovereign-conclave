"""M6 HTTP e2e tests: SSE streaming, public verify endpoints, token auth, appeals.

Each test boots a real ``ServerApp`` behind ``ThreadingHTTPServer`` on an
ephemeral port and drives cases through the HTTP verbs exactly as the
roadmap's endpoint contract describes: writes are token-authed, reads are
civic-public, ``/watch`` streams DeliberationEvents over SSE, and the
appeal bridge files/screen petitions through the M5 engine.
"""

from __future__ import annotations

import base64
import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "scripts"), str(ROOT / "tests")):
    if path not in sys.path:
        sys.path.insert(0, path)

from conclave_core.artifacts import raw_cid  # noqa: E402
from conclave_core.cbor import decode  # noqa: E402
from conclave_core.cid import parse  # noqa: E402
from conclave_core.merkle import verify_inclusion  # noqa: E402
from conclave_core.verifier import verify_bundle  # noqa: E402
from conclave_server.http import ServerApp, make_server  # noqa: E402
from test_emit_bundle import LEDGER_ENTRIES  # canonical emit fixtures

ROSTER_PATH = ROOT / "configs" / "conclave-roster.json"

PETITION_DOCUMENTS = [
    {
        "item": (
            "County audit office note: precinct 12's 2026-03-14 tally amendment "
            "carries no countersignature; the recorded margin is unsupported."
        ),
        "source": "county-audit-office",
        "source_type": "imported",
        "handling": "presented to the panel archive",
        "sensitivity": "restricted",
    },
    {
        "item": (
            "Sworn statement from the poll office clerk: the missing "
            "countersignature was never executed in the office's presence."
        ),
        "source": "poll-office-clerk",
        "source_type": "imported",
        "handling": "presented to the panel archive",
        "sensitivity": "restricted",
    },
]


class HttpFixture(unittest.TestCase):
    """Boots one real server per test on an ephemeral loopback port."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.app = ServerApp(self.root / "keys", self.root / "store.sqlite3", ROSTER_PATH)
        self.server = make_server(self.app, "127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.app.close()
        self._tmp.cleanup()

    # -- HTTP helpers ---------------------------------------------------------

    def _request(self, method: str, path: str, body: dict | None = None, token: str | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Conclave-Token"] = token
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        parsed = None
        if data:
            try:
                parsed = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = {"_raw": data}
        return response.status, parsed

    def _post(self, path: str, body: dict, token: str | None = None):
        return self._request("POST", path, body, token)

    def _get(self, path: str):
        return self._request("GET", path)

    def _raw_get(self, path: str):
        """GET that returns the raw bytes (for /artifact CBOR bodies)."""

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
        conn.request("GET", path)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, response.getheader("Content-Type"), data

    def _read_sse(self, path: str, max_events: int = 400) -> list[dict]:
        """Read one SSE stream from /watch until a terminal or timeout cap."""

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=180)
        conn.request("GET", path)
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "text/event-stream")
        events: list[dict] = []
        try:
            while len(events) < max_events:
                line = response.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text.startswith("data: "):
                    continue
                event = json.loads(text[len("data: "):])
                events.append(event)
                if event["kind"] in ("closed", "aborted"):
                    break
        finally:
            conn.close()
        return events

    # -- cases under test -------------------------------------------------------

    def _convene(
        self, *, profile: str, timestamp: str, problem="Adopt variant B? (http e2e)", **extra
    ) -> dict:
        status, payload = self._post(
            "/convene",
            {
                "problem": problem,
                "profile": profile,
                "ledgerDraft": LEDGER_ENTRIES,
                "timestamp": timestamp,
                **extra,
            },
        )
        self.assertEqual(status, 201, payload)
        self.assertIn("token", payload)
        self.assertIn("caseRef", payload)
        return payload

    def _await_terminal(self, case_ref: str, deadline_s: float = 120.0) -> None:
        end = time.monotonic() + deadline_s
        while time.monotonic() < end:
            status = self.app.store.session(case_ref)
            if status is not None and json.loads(status["position"]) in (
                ["closed"], ["aborted"]
            ):
                return
            time.sleep(0.05)
        self.fail(f"case {case_ref} did not terminate in {deadline_s}s")


class ConveneWatchVerdictTests(HttpFixture):
    def test_sse_stream_replays_full_lifecycle_and_closes(self):
        conv = self._convene(profile="architecture", timestamp="2026-10-21T09:00:00Z")
        events = self._read_sse(f"/watch?caseRef={conv['caseRef']}&timeout=120")
        kinds = [event["kind"] for event in events]
        self.assertEqual(
            kinds,
            ["convened", "round-started", "turn-committed", "turn-committed",
             "turn-committed", "turn-committed", "turn-committed", "turn-committed",
             "turn-committed", "summary", "consensus-score", "verdict", "closed"],
        )
        ordinals = [event["ordinal"] for event in events]
        self.assertEqual(ordinals, list(range(1, len(ordinals) + 1)))

        # a second watcher resuming just before the verdict replays the tail
        verdict_ordinal = next(
            event["ordinal"] for event in events if event["kind"] == "verdict"
        )
        tail = self._read_sse(
            f"/watch?caseRef={conv['caseRef']}&after={verdict_ordinal - 1}&timeout=15"
        )
        self.assertEqual([event["kind"] for event in tail], ["verdict", "closed"])

        status, payload = self._get(f"/verdict?caseRef={conv['caseRef']}")
        self.assertEqual(status, 200)
        self.assertEqual(payload["caseRef"], conv["caseRef"])
        self.assertTrue(payload["verdictCid"].startswith("bafy"))
        self.assertEqual(payload["appealCid"], None)
        self.assertEqual(payload["dissentCids"], [])

    def test_verdict_conflicts_before_terminal(self):
        conv = self._convene(profile="strategy", timestamp="2026-10-21T11:00:00Z")
        status, payload = self._get(f"/verdict?caseRef={conv['caseRef']}")
        self.assertEqual(status, 409)
        self.assertIn("no verdict yet", payload["error"])
        status, payload = self._get("/verdict?caseRef=case-nonexistent-2026")
        self.assertEqual(status, 404)


class ConcurrentDeliberationTests(HttpFixture):
    def test_two_deliberations_stream_in_parallel_and_both_verify(self):
        first = self._convene(profile="architecture", timestamp="2026-10-21T12:00:00Z")
        second = self._convene(profile="strategy", timestamp="2026-10-21T13:00:00Z")
        self.assertNotEqual(first["caseRef"], second["caseRef"])

        streams: dict[str, list[dict]] = {}
        errors: list[Exception] = []

        def stream(case_ref: str) -> None:
            try:
                streams[case_ref] = self._read_sse(
                    f"/watch?caseRef={case_ref}&timeout=180"
                )
            except Exception as error:  # surfaced for the assertion below
                errors.append(error)

        threads = [
            threading.Thread(target=stream, args=(first["caseRef"],)),
            threading.Thread(target=stream, args=(second["caseRef"],)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(240)
        self.assertEqual(errors, [])
        for case_ref, events in streams.items():
            self.assertEqual(events[-1]["kind"], "closed", case_ref)
            self.assertIn("verdictCid", events[-1]["payload"], case_ref)

        for case_ref in (first["caseRef"], second["caseRef"]):
            status, payload = self._get(f"/verdict?caseRef={case_ref}")
            self.assertEqual(status, 200, payload)
            self._await_terminal(case_ref)

        # both cases materialize and verify independently after live traffic
        verdicts = []
        for index, case_ref in enumerate((first["caseRef"], second["caseRef"])):
            with tempfile.TemporaryDirectory() as out:
                bundle = self.app.materialize(case_ref, Path(out) / "case")
                problems, summary = verify_bundle(bundle)
                self.assertEqual(problems, [], f"{case_ref}: {summary}")
            status, payload = self._get(f"/verdict?caseRef={case_ref}")
            verdicts.append((case_ref, payload["verdictCid"]))
        self.assertNotEqual(verdicts[0][1], verdicts[1][1])


class PublicVerifyEndpointTests(HttpFixture):
    def setUp(self) -> None:
        super().setUp()
        self.conv = self._convene(
            profile="architecture",
            timestamp="2026-10-21T14:30:00Z",
            problem="Should the county publish the ledger? (public endpoints)",
        )
        self._await_terminal(self.conv["caseRef"])

    def test_artifact_bytes_serve_cbor(self):
        status, verdict = self._get(f"/verdict?caseRef={self.conv['caseRef']}")
        self.assertEqual(status, 200)
        code, media_type, raw = self._raw_get(f"/artifact/{verdict['verdictCid']}")
        self.assertEqual(code, 200)
        self.assertEqual(media_type, "application/cbor")
        artifact = decode(raw)
        self.assertEqual(artifact["type"], "Verdict")

    def test_prove_returns_verifiable_inclusion_proof(self):
        status, verdict = self._get(f"/verdict?caseRef={self.conv['caseRef']}")
        self.assertEqual(status, 200)
        proven_ref = verdict["verdictCid"]
        code, prove = self._get(f"/prove/{proven_ref}?caseRef={self.conv['caseRef']}")
        self.assertEqual(code, 200)
        self.assertEqual(prove["caseRef"], self.conv["caseRef"])
        self.assertEqual(prove["leafCid"], proven_ref)

        code, sth = self._get(f"/latestSTH?caseRef={self.conv['caseRef']}")
        self.assertEqual(code, 200)
        self.assertEqual(sth["treeSize"], prove["treeSize"])

        cid = parse(proven_ref)
        audit = [base64.b64decode(node) for node in prove["path"]]
        verified = verify_inclusion(
            cid.cid_bytes(),
            prove["index"],
            audit,
            prove["treeSize"],
            base64.b64decode(sth["rootHash"]),
        )
        self.assertTrue(verified)

        # a well-formed but never-logged CID is a clean 404
        never = str(raw_cid(b"never-minted-artifact-for-prove"))
        status, payload = self._get(f"/prove/{never}")
        self.assertEqual(status, 404)
        self.assertIn("not a logged leaf", payload["error"])

    def test_turn_cid_is_not_a_logged_leaf(self):
        rows = self.app.store.by_type("Turn")
        self.assertTrue(rows)
        turn_ref = str(rows[0])
        status, payload = self._get(f"/prove/{turn_ref}")
        self.assertEqual(status, 404)
        self.assertIn("not a logged leaf", payload["error"])

        # the artifact itself is publicly readable even when un-logged
        code, media_type, raw = self._raw_get(f"/artifact/{turn_ref}")
        self.assertEqual(code, 200)
        self.assertEqual(media_type, "application/cbor")

        # unknown cases are clean 404s across the log endpoints
        status, payload = self._get("/latestSTH?caseRef=case-nonexistent-2026")
        self.assertEqual(status, 404)
        never = str(raw_cid(b"never-minted-artifact-bytes"))
        status, payload = self._get(f"/artifact/{never}")
        self.assertEqual(status, 404)
        self.assertIn("unknown artifact", payload["error"])


class TokenAuthTests(HttpFixture):
    def setUp(self) -> None:
        super().setUp()
        self.conv = self._convene(
            profile="architecture", timestamp="2026-10-21T15:00:00Z",
            problem="Auth probe case",
        )
        self._await_terminal(self.conv["caseRef"])

    def test_petition_requires_the_session_token(self):
        case_ref = self.conv["caseRef"]
        body = {
            "caseRef": case_ref,
            "trigger": "T1",
            "grounds": "New evidence changes the record.",
            "documents": PETITION_DOCUMENTS,
        }
        status, payload = self._post("/petition", body)  # no header
        self.assertEqual(status, 401)
        status, payload = self._post("/petition", body, token="wrong-token")
        self.assertEqual(status, 401)

    def test_petition_rejects_unknown_case(self):
        status, payload = self._post(
            "/petition",
            {"caseRef": "case-unknown-2026", "trigger": "T1",
             "grounds": "x", "documents": PETITION_DOCUMENTS},
            token="anything",
        )
        self.assertEqual(status, 404)

    def test_reads_civic_public_without_tokens(self):
        case = self.conv["caseRef"]
        self.assertEqual(self._get(f"/verdict?caseRef={case}")[0], 200)
        self.assertEqual(self._get(f"/latestSTH?caseRef={case}")[0], 200)
        status, payload = self._get(f"/watch?caseRef={case}&after=99&timeout=1")
        self.assertEqual(status, 200)  # resumption is public too

    def test_watch_unknown_case_is_404_before_streaming(self):
        status, payload = self._get("/watch?caseRef=case-ghost-2026&timeout=1")
        self.assertEqual(status, 404)
        self.assertIn("unknown case", payload["error"])


class PetitionScreeningE2ETests(HttpFixture):
    def test_t1_petition_and_admitted_screening_grow_the_case_log(self):
        conv = self._convene(
            profile="architecture",
            timestamp="2026-10-21T16:00:00Z",
            problem="Election appeal sandbox: the tally margin is contested (T1).",
        )
        case_ref = conv["caseRef"]
        self._await_terminal(case_ref)

        leaves_before = self.app.store.leaf_count(case_ref)
        self.assertGreaterEqual(leaves_before, 1)

        status, petition = self._post(
            "/petition",
            {
                "caseRef": case_ref,
                "trigger": "T1",
                "grounds": "The county clerk produced unsigned supplemental counts.",
                "documents": PETITION_DOCUMENTS,
                "filedBy": "petitioner-clerk",
            },
            token=conv["token"],
        )
        self.assertEqual(status, 201, petition)
        self.assertEqual(petition["trigger"], "T1")
        appeal_ref = petition["appealRef"]
        self.assertTrue(appeal_ref.startswith("bafy"))
        self.assertTrue(petition["supplementRef"].startswith("bafy"))

        status, screening = self._post(
            "/screening",
            {
                "caseRef": case_ref,
                "appealRef": appeal_ref,
                "decision": "admitted",
                "screenedBy": "conclave-marshall",
                "reasons": "Material evidence accepted: unsigned counts clearly affect the margin.",
            },
            token=conv["token"],
        )
        self.assertEqual(status, 201, screening)
        self.assertEqual(screening["decision"], "admitted")

        # the log grew by the supplement ledger, the appeal, and the screening
        leaves_after = self.app.store.leaf_count(case_ref)
        self.assertEqual(leaves_after, leaves_before + 3)
        logged = [str(leaf) for leaf in self.app.store.leaves(case_ref)]
        self.assertIn(appeal_ref, logged)
        self.assertIn(screening["screeningRef"], logged)
        self.assertIn(petition["supplementRef"], logged)

        # appeal artifacts are publicly readable, and the full bundle still verifies
        code, media_type, raw = self._raw_get(f"/artifact/{appeal_ref}")
        self.assertEqual(code, 200)
        self.assertEqual(media_type, "application/cbor")
        appeal_artifact = decode(raw)
        self.assertEqual(appeal_artifact["type"], "Appeal")
        self.assertEqual(str(appeal_artifact["supplementLedger"]), petition["supplementRef"])

        with tempfile.TemporaryDirectory() as out:
            bundle = self.app.materialize(case_ref, Path(out) / "case")
            problems, summary = verify_bundle(bundle)
            self.assertEqual(problems, [], f"post-appeal bundle: {summary}")

    def test_t1_without_documents_is_unprocessable(self):
        conv = self._convene(
            profile="strategy",
            timestamp="2026-10-21T17:00:00Z",
            problem="T1 guard probe case",
        )
        self._await_terminal(conv["caseRef"])
        status, payload = self._post(
            "/petition",
            {"caseRef": conv["caseRef"], "trigger": "T1", "grounds": "no docs attached"},
            token=conv["token"],
        )
        self.assertEqual(status, 422)

    def test_screening_decision_is_validator_constrained(self):
        conv = self._convene(
            profile="architecture",
            timestamp="2026-10-21T18:00:00Z",
            problem="Screening validation probe case",
        )
        self._await_terminal(conv["caseRef"])
        status, payload = self._post(
            "/screening",
            {"caseRef": conv["caseRef"], "appealRef": "bafy" + "0" * 20,
             "decision": "maybe", "reasons": "indecisive"},
            token=conv["token"],
        )
        self.assertEqual(status, 400)


class ConveneValidationTests(HttpFixture):
    def test_missing_problem_is_400(self):
        status, payload = self._post("/convene", {"profile": "architecture"})
        self.assertEqual(status, 400)

    def test_unknown_profile_is_400(self):
        status, payload = self._post(
            "/convene", {"problem": "x", "profile": "no-such-profile"}
        )
        self.assertEqual(status, 400)
        self.assertIn("unknown profile", payload["error"])

    def test_unknown_protocol_param_is_400(self):
        status, payload = self._post(
            "/convene",
            {"problem": "x", "profile": "architecture",
             "protocolParams": {"maxRounds": 2, "bogusField": 1}},
        )
        self.assertEqual(status, 400)
        self.assertIn("bogusField", payload["error"])

    def test_agent_markdown_for_unknown_seat_is_400(self):
        status, payload = self._post(
            "/convene",
            {"problem": "x", "profile": "architecture",
             "agentMarkdown": {"conclave-ghost-seat": "### nothing"}},
        )
        self.assertEqual(status, 400)
        self.assertIn("unknown seat", payload["error"])


if __name__ == "__main__":
    unittest.main()
