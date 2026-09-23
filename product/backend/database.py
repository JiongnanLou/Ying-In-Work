from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    score REAL,
                    confidence REAL,
                    metrics_json TEXT NOT NULL,
                    suggestions_json TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS work_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    status TEXT NOT NULL DEFAULT 'active'
                );
                CREATE TABLE IF NOT EXISTS work_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    activity TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES work_sessions(id)
                );
                """
            )

    def add_analysis(self, kind: str, result: dict[str, Any], provider: str) -> int:
        with self.connect() as db:
            cursor = db.execute(
                """INSERT INTO analyses
                (kind, summary, score, confidence, metrics_json, suggestions_json, provider, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    kind,
                    result["summary"],
                    result.get("score"),
                    result.get("confidence", 0),
                    json.dumps(result.get("metrics", {}), ensure_ascii=False),
                    json.dumps(result.get("suggestions", []), ensure_ascii=False),
                    provider,
                    utc_now(),
                ),
            )
            return int(cursor.lastrowid)

    def start_work(self) -> int:
        with self.connect() as db:
            active = db.execute(
                "SELECT id FROM work_sessions WHERE status = 'active' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if active:
                return int(active["id"])
            cursor = db.execute(
                "INSERT INTO work_sessions (started_at, status) VALUES (?, 'active')", (utc_now(),)
            )
            return int(cursor.lastrowid)

    def active_work_session(self) -> int | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT id FROM work_sessions WHERE status = 'active' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return int(row["id"]) if row else None

    def add_work_sample(self, session_id: int, result: dict[str, Any]) -> None:
        with self.connect() as db:
            db.execute(
                """INSERT INTO work_samples
                (session_id, activity, confidence, note, created_at) VALUES (?, ?, ?, ?, ?)""",
                (
                    session_id,
                    result.get("activity", "unknown"),
                    result.get("confidence", 0),
                    result.get("summary", ""),
                    utc_now(),
                ),
            )

    def end_work(self) -> int | None:
        session_id = self.active_work_session()
        if session_id is None:
            return None
        with self.connect() as db:
            db.execute(
                "UPDATE work_sessions SET ended_at = ?, status = 'completed' WHERE id = ?",
                (utc_now(), session_id),
            )
        return session_id

    def dashboard(self) -> dict[str, Any]:
        with self.connect() as db:
            recent_rows = db.execute(
                "SELECT * FROM analyses ORDER BY id DESC LIMIT 20"
            ).fetchall()
            recent = []
            for row in recent_rows:
                item = dict(row)
                item["metrics"] = json.loads(item.pop("metrics_json"))
                item["suggestions"] = json.loads(item.pop("suggestions_json"))
                recent.append(item)

            totals = {
                row["kind"]: row["count"]
                for row in db.execute(
                    "SELECT kind, COUNT(*) AS count FROM analyses GROUP BY kind"
                ).fetchall()
            }
            active = self.active_work_session()
            work = db.execute(
                """SELECT ws.id, ws.started_at, ws.ended_at, ws.status,
                   COUNT(s.id) AS samples,
                   SUM(CASE WHEN s.activity = 'focused' THEN 1 ELSE 0 END) AS focused,
                   SUM(CASE WHEN s.activity = 'phone' THEN 1 ELSE 0 END) AS phone,
                   SUM(CASE WHEN s.activity = 'away' THEN 1 ELSE 0 END) AS away
                   FROM work_sessions ws LEFT JOIN work_samples s ON s.session_id = ws.id
                   GROUP BY ws.id ORDER BY ws.id DESC LIMIT 10"""
            ).fetchall()
            return {
                "recent": recent,
                "totals": totals,
                "active_work_session": active,
                "work_sessions": [dict(row) for row in work],
            }

    def clear_all(self) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM work_samples")
            db.execute("DELETE FROM work_sessions")
            db.execute("DELETE FROM analyses")
