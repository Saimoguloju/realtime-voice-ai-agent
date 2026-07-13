#
# SQLite persistence for call sessions, transcripts, and latency metrics.
#

"""Storage layer for the voice agent.

Persists every call session, its transcript, and per-service latency metrics
(TTFB / processing time) to a local SQLite database so they can be reviewed
later through the dashboard API.
"""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "voice_agent.db"

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                ended_at   TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS metrics (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                processor   TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value_secs  REAL NOT NULL,
                created_at  TEXT NOT NULL
            );
            """
        )
        _conn.commit()
    return _conn


def start_session(session_id: str) -> None:
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO sessions (session_id, started_at) VALUES (?, ?)",
            (session_id, _now()),
        )
        conn.commit()


def end_session(session_id: str) -> None:
    with _lock:
        conn = _get_conn()
        conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE session_id = ?",
            (_now(), session_id),
        )
        conn.commit()


def add_message(session_id: str, role: str, content: str) -> None:
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, _now()),
        )
        conn.commit()


def record_metric(session_id: str, processor: str, metric_type: str, value_secs: float) -> None:
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO metrics (session_id, processor, metric_type, value_secs, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (session_id, processor, metric_type, value_secs, _now()),
        )
        conn.commit()


def list_sessions(limit: int = 50) -> list[dict]:
    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            """
            SELECT s.session_id, s.started_at, s.ended_at,
                   COUNT(m.id) AS message_count
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.session_id
            GROUP BY s.session_id
            ORDER BY s.started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_transcript(session_id: str) -> list[dict]:
    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages"
            " WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(int(len(sorted_values) * pct), len(sorted_values) - 1)
    return sorted_values[idx]


def get_metrics_summary(session_id: str | None = None) -> list[dict]:
    """Aggregate latency stats (count / avg / p50 / p95) per processor and metric type."""
    with _lock:
        conn = _get_conn()
        if session_id:
            rows = conn.execute(
                "SELECT processor, metric_type, value_secs FROM metrics WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT processor, metric_type, value_secs FROM metrics"
            ).fetchall()

    grouped: dict[tuple[str, str], list[float]] = {}
    for r in rows:
        grouped.setdefault((r["processor"], r["metric_type"]), []).append(r["value_secs"])

    summary = []
    for (processor, metric_type), values in sorted(grouped.items()):
        values.sort()
        summary.append(
            {
                "processor": processor,
                "metric_type": metric_type,
                "count": len(values),
                "avg_secs": round(sum(values) / len(values), 4),
                "p50_secs": round(_percentile(values, 0.50), 4),
                "p95_secs": round(_percentile(values, 0.95), 4),
            }
        )
    return summary
