import asyncio
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

DB_PATH = os.getenv("DATABASE_PATH", "instagram_auto.db")
_db_lock = asyncio.Lock()
_connection: Optional[sqlite3.Connection] = None


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(db_path, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL;")
        _connection.execute("PRAGMA foreign_keys=ON;")
    return _connection


def close_db() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def init_db(db_path: str = DB_PATH) -> None:
    conn = get_connection(db_path)
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rules (
                rule_id TEXT PRIMARY KEY,
                keyword TEXT NOT NULL,
                dm_message TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dm_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                comment_id TEXT NOT NULL,
                post_id TEXT NOT NULL,
                status TEXT NOT NULL,
                dm_id TEXT,
                attempts INTEGER DEFAULT 0,
                last_error TEXT,
                created_at REAL NOT NULL,
                next_attempt_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                UNIQUE (user_id, rule_id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blocked_duplicates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )


async def add_rule(rule_id: str, keyword: str, dm_message: str) -> Dict[str, str]:
    now = time.time()
    async with _db_lock:
        conn = get_connection()
        with conn:
            conn.execute(
                "INSERT INTO rules (rule_id, keyword, dm_message, created_at) VALUES (?, ?, ?, ?)",
                (rule_id, keyword, dm_message, now),
            )
    return {"rule_id": rule_id, "keyword": keyword, "dm_message": dm_message}


async def get_matching_rules(comment_text: str) -> List[Dict[str, Any]]:
    lowered_text = comment_text.lower()
    async with _db_lock:
        conn = get_connection()
        cursor = conn.execute("SELECT rule_id, keyword, dm_message FROM rules")
        rows = cursor.fetchall()

    matching = []
    for row in rows:
        if row["keyword"].lower() in lowered_text:
            matching.append(
                {
                    "rule_id": row["rule_id"],
                    "keyword": row["keyword"],
                    "dm_message": row["dm_message"],
                }
            )
    return matching


async def insert_dm_attempt_or_dedup(
    event_id: str, user_id: str, rule_id: str, comment_id: str, post_id: str
) -> bool:
    """
    Design decision 2: Atomic deduplication via UNIQUE (user_id, rule_id) constraint.
    SQLite serializes writers, so ON CONFLICT DO NOTHING prevents race conditions.
    If rowcount == 0, record in blocked_duplicates table.
    Returns True if inserted (new attempt), False if blocked duplicate.
    """
    now = time.time()
    async with _db_lock:
        conn = get_connection()
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO dm_attempts (user_id, rule_id, comment_id, post_id, status, created_at, next_attempt_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
                ON CONFLICT (user_id, rule_id) DO NOTHING;
                """,
                (user_id, rule_id, comment_id, post_id, now, now, now),
            )
            if cursor.rowcount > 0:
                return True

            conn.execute(
                """
                INSERT INTO blocked_duplicates (event_id, user_id, rule_id, created_at)
                VALUES (?, ?, ?, ?);
                """,
                (event_id, user_id, rule_id, now),
            )
            return False


async def cancel_pending_attempt(comment_id: str) -> bool:
    """
    Design decision 4: comment.deleted only cancels attempts still in 'pending' status.
    If in_flight or delivered, leave it.
    """
    now = time.time()
    async with _db_lock:
        conn = get_connection()
        with conn:
            cursor = conn.execute(
                """
                UPDATE dm_attempts
                SET status = 'cancelled', updated_at = ?
                WHERE comment_id = ? AND status = 'pending';
                """,
                (now, comment_id),
            )
            return cursor.rowcount > 0


async def get_pending_attempts(limit: int = 10) -> List[Dict[str, Any]]:
    now = time.time()
    async with _db_lock:
        conn = get_connection()
        cursor = conn.execute(
            """
            SELECT a.id, a.user_id, a.rule_id, a.comment_id, a.attempts, r.dm_message
            FROM dm_attempts a
            JOIN rules r ON a.rule_id = r.rule_id
            WHERE a.status = 'pending' AND a.next_attempt_at <= ?
            ORDER BY a.created_at ASC
            LIMIT ?;
            """,
            (now, limit),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


async def update_attempt_status(
    attempt_id: int,
    status: str,
    dm_id: Optional[str] = None,
    next_attempt_at: Optional[float] = None,
    last_error: Optional[str] = None,
    increment_attempts: bool = False,
) -> None:
    now = time.time()
    next_time = next_attempt_at if next_attempt_at is not None else now
    async with _db_lock:
        conn = get_connection()
        with conn:
            if increment_attempts:
                conn.execute(
                    """
                    UPDATE dm_attempts
                    SET status = ?,
                        dm_id = COALESCE(?, dm_id),
                        attempts = attempts + 1,
                        next_attempt_at = ?,
                        last_error = ?,
                        updated_at = ?
                    WHERE id = ?;
                    """,
                    (status, dm_id, next_time, last_error, now, attempt_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE dm_attempts
                    SET status = ?,
                        dm_id = COALESCE(?, dm_id),
                        next_attempt_at = ?,
                        last_error = ?,
                        updated_at = ?
                    WHERE id = ?;
                    """,
                    (status, dm_id, next_time, last_error, now, attempt_id),
                )


async def get_in_flight_attempts(older_than_seconds: float = 30.0) -> List[Dict[str, Any]]:
    cutoff = time.time() - older_than_seconds
    async with _db_lock:
        conn = get_connection()
        cursor = conn.execute(
            """
            SELECT id, user_id, rule_id, comment_id, dm_id, attempts
            FROM dm_attempts
            WHERE status = 'in_flight' AND updated_at <= ? AND dm_id IS NOT NULL;
            """,
            (cutoff,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


async def get_stats() -> Dict[str, int]:
    """
    Design decision 1: /stats is computed directly from persisted SQLite tables.
    """
    async with _db_lock:
        conn = get_connection()
        cursor = conn.execute(
            """
            SELECT status, COUNT(*) as cnt
            FROM dm_attempts
            GROUP BY status;
            """
        )
        status_counts = {row["status"]: row["cnt"] for row in cursor.fetchall()}

        cursor = conn.execute("SELECT COUNT(*) as cnt FROM blocked_duplicates;")
        duplicates_blocked = cursor.fetchone()["cnt"]

    sent = status_counts.get("delivered", 0)
    failed = status_counts.get("failed", 0)
    queued = status_counts.get("pending", 0) + status_counts.get("in_flight", 0)

    return {
        "sent": sent,
        "failed": failed,
        "queued": queued,
        "duplicates_blocked": duplicates_blocked,
    }
