"""Artifact store, projections, and transparency-log tables for the conclave
server (roadmap M6).

Deployment note (documented deviation): production targets Postgres and
Memorystore; this repo's dependency budget is stdlib-only beyond the
OpenSSL-backed ``cryptography`` package, so v0.2 ships the same schema
shape and invariants on stdlib SQLite per the roadmap's single-codebase
decision (the Dart/Serverpod variant defers to v0.3+).

Invariants:
- ``artifacts`` is append-only and content-addressed: rows are never
  updated and never deleted; re-ingesting an existing CID is a no-op, so
  the first ``created_at`` stands.
- Projections (manifests, rounds, turns, verdicts, appeals) are pure
  indexes over artifact CIDs and fully rebuildable from ``artifacts``.
- The transparency log is case-scoped (one Merkle log per conclave): it
  stores one leaf row per entry plus a head per tree size; intermediate
  Merkle nodes recompute from leaf CIDs on demand.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from conclave_core.artifacts import artifact_bytes, artifact_cid
from conclave_core.cbor import decode
from conclave_core.cid import Cid, parse
from conclave_core.merkle import consistency_proof, path, tree_hash

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS artifacts (
        cid        TEXT PRIMARY KEY,
        artifact   BLOB NOT NULL,
        type       TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS artifacts_type ON artifacts (type)",
    """
    CREATE TABLE IF NOT EXISTS proj_manifests (
        manifest_cid TEXT PRIMARY KEY,
        case_id      TEXT NOT NULL,
        verdict_cid  TEXT,
        supersedes   TEXT,
        created_at   TEXT NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS proj_rounds (
        round_cid   TEXT PRIMARY KEY,
        round_index INTEGER NOT NULL,
        prev_cid    TEXT,
        status      TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS proj_turns (
        turn_cid    TEXT PRIMARY KEY,
        round_index INTEGER NOT NULL,
        seat_id     TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS proj_verdicts (
        verdict_cid  TEXT PRIMARY KEY,
        manifest_cid TEXT NOT NULL,
        issued_at    TEXT NOT NULL,
        created_at   TEXT NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS proj_appeals (
        appeal_cid  TEXT PRIMARY KEY,
        verdict_cid TEXT NOT NULL,
        trigger     TEXT NOT NULL,
        filed_at    TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS log_entries (
        case_ref   TEXT NOT NULL,
        tree_index INTEGER NOT NULL,
        cid        TEXT NOT NULL,
        logged_at  TEXT NOT NULL,
        PRIMARY KEY (case_ref, tree_index),
        UNIQUE (case_ref, cid)
    )""",
    """
    CREATE TABLE IF NOT EXISTS signed_tree_heads (
        case_ref     TEXT NOT NULL,
        tree_size    INTEGER NOT NULL,
        root_hash    BLOB NOT NULL,
        published_at TEXT NOT NULL,
        PRIMARY KEY (case_ref, tree_size)
    )""",
    """
    CREATE TABLE IF NOT EXISTS payloads (
        name       TEXT PRIMARY KEY,   -- '<raw-cid>.raw' resolvable input/output bytes
        payload    BLOB NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS sessions (
        case_ref    TEXT PRIMARY KEY,
        position    TEXT NOT NULL,      -- orchestration FSM position (JSON)
        state       TEXT NOT NULL,      -- orchestration state blob (JSON)
        tokens_used INTEGER NOT NULL,
        updated_at  TEXT NOT NULL
    )""",
)

_PROJECTIONS = ("proj_manifests", "proj_rounds", "proj_turns", "proj_verdicts", "proj_appeals")


class ArtifactStore:
    """Append-only artifact persistence with projections and a Merkle log.

    Safe for concurrent use by server threads: every operation runs inside
    one sqlite connection guarded by a lock, so SQL ordering is absolute.
    """

    def __init__(self, path: Path) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            for statement in _SCHEMA:
                self._conn.execute(statement)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _fetch(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _scalar(self, sql: str, params: tuple = ()) -> Any:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()[0]

    # -- artifacts -----------------------------------------------------------

    def ingest(self, artifact: dict, created_at: str) -> Cid:
        """Validate + store canonical bytes under the artifact's CID."""

        canonical = artifact_bytes(artifact)  # validates the artifact
        cid = artifact_cid(artifact)
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO artifacts (cid, artifact, type, created_at) "
                "VALUES (?, ?, ?, ?)",
                (str(cid), canonical, str(artifact.get("type")), created_at),
            )
            self._project(cid, artifact, created_at)
            self._conn.commit()
        return cid

    def _project(self, cid: Cid, artifact: dict, created_at: str) -> None:
        """Index one freshly ingested artifact projection (inside the lock)."""

        type_name = str(artifact.get("type"))
        if type_name == "DeliberationManifest":
            self._conn.execute(
                "INSERT OR IGNORE INTO proj_manifests (manifest_cid, case_id, verdict_cid, "
                "supersedes, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    str(cid),
                    str(artifact["caseId"]),
                    str(artifact["verdict"]),
                    str(artifact.get("supersedes")),
                    created_at,
                ),
            )
        elif type_name == "Round":
            self._conn.execute(
                "INSERT OR IGNORE INTO proj_rounds (round_cid, round_index, prev_cid, status, "
                "created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    str(cid),
                    int(artifact["index"]),
                    str(artifact.get("prev")),
                    str(artifact["status"]),
                    created_at,
                ),
            )
        elif type_name == "Turn":
            self._conn.execute(
                "INSERT OR IGNORE INTO proj_turns (turn_cid, round_index, seat_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                (str(cid), int(artifact["roundIndex"]), str(artifact["seatId"]), created_at),
            )
        elif type_name == "Verdict":
            self._conn.execute(
                "INSERT OR IGNORE INTO proj_verdicts (verdict_cid, manifest_cid, issued_at, "
                "created_at) VALUES (?, ?, ?, ?)",
                (str(cid), str(artifact["manifest"]), str(artifact["issuedAt"]), created_at),
            )
        elif type_name == "Appeal":
            self._conn.execute(
                "INSERT OR IGNORE INTO proj_appeals (appeal_cid, verdict_cid, trigger, filed_at, "
                "created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    str(cid),
                    str(artifact["verdict"]),
                    str(artifact["trigger"]),
                    str(artifact["filedAt"]),
                    created_at,
                ),
            )

    def get(self, cid: str | Cid) -> dict | None:
        rows = self._fetch("SELECT artifact FROM artifacts WHERE cid = ?", (str(cid),))
        if not rows:
            return None
        return decode(bytes(rows[0]["artifact"]))

    def raw(self, cid: str | Cid) -> bytes | None:
        rows = self._fetch("SELECT artifact FROM artifacts WHERE cid = ?", (str(cid),))
        return bytes(rows[0]["artifact"]) if rows else None

    def has(self, cid: str | Cid) -> bool:
        return bool(self._fetch("SELECT 1 FROM artifacts WHERE cid = ?", (str(cid),)))

    def created_at(self, cid: str | Cid) -> str | None:
        rows = self._fetch("SELECT created_at FROM artifacts WHERE cid = ?", (str(cid),))
        return rows[0]["created_at"] if rows else None

    def all_cids(self) -> list[Cid]:
        rows = self._fetch("SELECT cid FROM artifacts ORDER BY created_at, cid")
        return [parse(row["cid"]) for row in rows]

    def by_type(self, type_name: str) -> list[Cid]:
        rows = self._fetch(
            "SELECT cid FROM artifacts WHERE type = ? ORDER BY created_at, cid", (type_name,)
        )
        return [parse(row["cid"]) for row in rows]

    def counts(self) -> dict[str, int]:
        rows = self._fetch("SELECT type, COUNT(*) AS n FROM artifacts GROUP BY type")
        return {row["type"]: row["n"] for row in rows}

    def rebuild_projections(self) -> dict[str, int]:
        """Wipe and re-derive every projection; returns row counts per table."""

        with self._lock:
            for table in _PROJECTIONS:
                self._conn.execute(f"DELETE FROM {table}")
            rows = self._conn.execute(
                "SELECT cid, artifact, created_at FROM artifacts ORDER BY rowid"
            ).fetchall()
            for row in rows:
                self._project(parse(row["cid"]), decode(bytes(row["artifact"])), row["created_at"])
            counts = {
                table: self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in _PROJECTIONS
            }
            self._conn.commit()
        return counts

    # -- transparency log (case-scoped; one Merkle log per conclave) ----------

    def append_log_leaf(self, cid: str | Cid, logged_at: str, *, case_ref: str) -> tuple[int, bytes]:
        """Log a leaf and append the head for the new tree size; returns (size, root).

        The leaf must reference an already-ingested artifact, and each CID is
        logged at most once per case. Logs are case-scoped so a case bundle
        materializes with exactly its own leaf sequence.
        """

        cid_str = str(cid)
        if not self.has(cid_str):
            raise ValueError(f"transparency log leaf missing from the artifact store: {cid_str}")
        with self._lock:
            existing = self._conn.execute(
                "SELECT 1 FROM log_entries WHERE case_ref = ? AND cid = ?", (case_ref, cid_str)
            ).fetchone()
            if existing:
                raise ValueError(f"artifact is already logged for case {case_ref}: {cid_str}")
            next_index = self._conn.execute(
                "SELECT COALESCE(MAX(tree_index), 0) + 1 FROM log_entries WHERE case_ref = ?",
                (case_ref,),
            ).fetchone()[0]
            if not isinstance(next_index, int):  # pragma: no cover - defensive
                raise ValueError("transparency log index corruption")
            self._conn.execute(
                "INSERT INTO log_entries (case_ref, tree_index, cid, logged_at) VALUES (?, ?, ?, ?)",
                (case_ref, next_index, cid_str, logged_at),
            )
            leaf_rows = self._conn.execute(
                "SELECT cid FROM log_entries WHERE case_ref = ? ORDER BY tree_index", (case_ref,)
            ).fetchall()
            leaf_cids = [parse(row["cid"]) for row in leaf_rows]
            root = tree_hash([leaf.cid_bytes() for leaf in leaf_cids])
            self._conn.execute(
                "INSERT OR REPLACE INTO signed_tree_heads (case_ref, tree_size, root_hash, "
                "published_at) VALUES (?, ?, ?, ?)",
                (case_ref, len(leaf_cids), root, logged_at),
            )
            self._conn.commit()
        return len(leaf_cids), root

    def leaves(self, case_ref: str) -> list[Cid]:
        rows = self._fetch(
            "SELECT cid FROM log_entries WHERE case_ref = ? ORDER BY tree_index", (case_ref,)
        )
        return [parse(row["cid"]) for row in rows]

    def head(self, case_ref: str, tree_size: int) -> tuple[bytes, str] | None:
        rows = self._fetch(
            "SELECT root_hash, published_at FROM signed_tree_heads WHERE case_ref = ? "
            "AND tree_size = ?",
            (case_ref, tree_size),
        )
        if not rows:
            return None
        return bytes(rows[0]["root_hash"]), rows[0]["published_at"]

    def heads(self, case_ref: str) -> list[tuple[int, bytes, str]]:
        rows = self._fetch(
            "SELECT tree_size, root_hash, published_at FROM signed_tree_heads WHERE case_ref = ? "
            "ORDER BY tree_size",
            (case_ref,),
        )
        return [(row["tree_size"], bytes(row["root_hash"]), row["published_at"]) for row in rows]

    def latest_head(self, case_ref: str) -> tuple[int, bytes, str] | None:
        heads = self.heads(case_ref)
        return heads[-1] if heads else None

    def consistency_proof(self, case_ref: str, m: int, n: int) -> list[bytes]:
        """RFC 6962 consistency proof between tree sizes ``m`` and ``n``."""

        if not 1 <= m <= n:
            raise ValueError("consistency proof requires 1 <= m <= n")
        current = self.leaf_count(case_ref)
        if n > current:
            raise ValueError(f"tree size {n} exceeds the log's {current} leaves")
        leaves = self.leaves(case_ref)[:n]
        return consistency_proof(m, [leaf.cid_bytes() for leaf in leaves])

    def inclusion_proof(self, case_ref: str, index: int, tree_size: int) -> list[bytes]:
        """RFC 6962 audit path for ``leaves[index]`` in the ``tree_size`` tree."""

        current = self.leaf_count(case_ref)
        if not 0 <= index < tree_size <= current:
            raise ValueError(
                f"invalid inclusion request: index {index} in tree of size {tree_size} "
                f"(log holds {current})"
            )
        leaves = self.leaves(case_ref)[:tree_size]
        return path(index, [leaf.cid_bytes() for leaf in leaves])

    def leaf_count(self, case_ref: str) -> int:
        return int(
            self._scalar(
                "SELECT COUNT(*) FROM log_entries WHERE case_ref = ?", (case_ref,)
            )
        )

    def leaf_case_refs(self, cid: str | Cid) -> list[str]:
        """Case refs whose transparency log carries ``cid`` as a leaf."""

        rows = self._fetch(
            "SELECT case_ref FROM log_entries WHERE cid = ? ORDER BY case_ref", (str(cid),)
        )
        return [row["case_ref"] for row in rows]

    # -- raw payloads ---------------------------------------------------------

    def ingest_payload(self, name: str, payload: bytes, created_at: str) -> None:
        """Store resolvable input/output bytes (``<raw-cid>.raw``) for offline replay.

        Like ``artifacts``, rows are keyed and never updated; re-ingesting is
        a no-op and the first ``created_at`` stands.
        """

        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO payloads (name, payload, created_at) VALUES (?, ?, ?)",
                (name, bytes(payload), created_at),
            )
            self._conn.commit()

    def payload(self, name: str) -> bytes | None:
        rows = self._fetch("SELECT payload FROM payloads WHERE name = ?", (name,))
        return bytes(rows[0]["payload"]) if rows else None

    def payload_names(self) -> list[str]:
        rows = self._fetch("SELECT name FROM payloads ORDER BY name")
        return [row["name"] for row in rows]

    # -- orchestration session rows -------------------------------------------

    def upsert_session(
        self, case_ref: str, position: str, state: str, tokens_used: int, updated_at: str
    ) -> None:
        """Persist the durable orchestration row for one case.

        ``position``/``state`` are JSON strings (FSM position and the case's
        state blob); ``sessions`` is derived server state, not part of the
        append-only artifact graph, so upserts are expected.
        """

        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO sessions (case_ref, position, state, tokens_used, "
                "updated_at) VALUES (?, ?, ?, ?, ?)",
                (case_ref, position, state, int(tokens_used), updated_at),
            )
            self._conn.commit()

    def session(self, case_ref: str) -> dict[str, Any] | None:
        rows = self._fetch(
            "SELECT position, state, tokens_used, updated_at FROM sessions WHERE case_ref = ?",
            (case_ref,),
        )
        if not rows:
            return None
        return {
            "position": rows[0]["position"],
            "state": rows[0]["state"],
            "tokens_used": int(rows[0]["tokens_used"]),
            "updated_at": rows[0]["updated_at"],
        }

    def session_refs(self) -> list[str]:
        rows = self._fetch("SELECT case_ref FROM sessions ORDER BY updated_at, case_ref")
        return [row["case_ref"] for row in rows]
