import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import CallRecord

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    project_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    tier TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    latency_ms INTEGER NOT NULL,
    success INTEGER NOT NULL,
    escalated INTEGER NOT NULL,
    confidence REAL,
    error_code TEXT,
    prompt_fingerprint TEXT
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_project_timestamp
    ON calls(project_id, timestamp);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(_CREATE_TABLE)
        conn.execute(_CREATE_INDEX)


def log_call(db_path: str, record: CallRecord) -> None:
    init_db(db_path)
    ts = record.timestamp.isoformat() if isinstance(record.timestamp, datetime) else record.timestamp
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO calls (
                timestamp, project_id, task_type, tier, model,
                input_tokens, output_tokens, cost_usd, latency_ms,
                success, escalated, confidence, error_code, prompt_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                record.project_id,
                record.task_type,
                record.tier,
                record.model,
                record.input_tokens,
                record.output_tokens,
                record.cost_usd,
                record.latency_ms,
                1 if record.success else 0,
                1 if record.escalated else 0,
                record.confidence,
                record.error_code,
                record.prompt_fingerprint,
            ),
        )


def get_spend_this_month(db_path: str, project_id: str) -> float:
    try:
        with _connect(db_path) as conn:
            now = datetime.utcnow()
            month_start = f"{now.year}-{now.month:02d}-01"
            row = conn.execute(
                """
                SELECT COALESCE(SUM(cost_usd), 0.0) AS total
                FROM calls
                WHERE project_id = ? AND timestamp >= ?
                """,
                (project_id, month_start),
            ).fetchone()
            return float(row["total"])
    except sqlite3.OperationalError:
        return 0.0


def get_recent_calls(db_path: str, project_id: str, n: int = 20) -> list[dict[str, Any]]:
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM calls
                WHERE project_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (project_id, n),
            ).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
