import sqlite3
import json
import threading
from contextlib import contextmanager

DB_PATH = "load_tests.db"
_lock = threading.Lock()


@contextmanager
def _get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                target_url TEXT,
                users INTEGER,
                spawn_rate INTEGER,
                duration_seconds INTEGER,
                status TEXT,
                stats_csv TEXT,
                stdout TEXT,
                stderr TEXT,
                error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT
            )
        """)


def create_job(job_id, target_url, users, spawn_rate, duration_seconds):
    with _lock, _get_conn() as conn:
        conn.execute(
            """INSERT INTO jobs (job_id, target_url, users, spawn_rate, duration_seconds, status)
               VALUES (?, ?, ?, ?, ?, 'queued')""",
            (job_id, target_url, users, spawn_rate, duration_seconds),
        )


def update_job(job_id, **fields):
    if not fields:
        return
    with _lock, _get_conn() as conn:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [job_id]
        if "status" in fields and fields["status"] in ("completed", "failed", "timeout"):
            set_clause += ", completed_at = CURRENT_TIMESTAMP"
        conn.execute(f"UPDATE jobs SET {set_clause} WHERE job_id = ?", values)


def get_job(job_id):
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def list_jobs(limit=50):
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT job_id, target_url, users, status, created_at, completed_at "
            "FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]