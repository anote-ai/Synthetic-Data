"""
Database layer — MySQL with connection pooling.
Gracefully degrades when DB_HOST is not configured (logs warning, never crashes).
"""
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_pool = None


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    host = os.getenv("DB_HOST")
    if not host:
        return None
    try:
        import mysql.connector.pooling as _pooling
        _pool = _pooling.MySQLConnectionPool(
            pool_name="synth_pool",
            pool_size=5,
            host=host,
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "synthetic_data"),
        )
        return _pool
    except Exception as e:
        logger.warning("DB pool init failed (non-fatal): %s", e)
        return None


def get_db_connection():
    """Return a connection from the pool, or None if DB is unavailable."""
    pool = _get_pool()
    if pool is None:
        return None
    try:
        return pool.get_connection()
    except Exception as e:
        logger.warning("DB connection failed (non-fatal): %s", e)
        return None


def user_id_for_email(conn, email: str) -> Optional[int]:
    """Upsert user by email and return their ID."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("INSERT INTO users (email) VALUES (%s)", (email,))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.warning("user_id_for_email failed (non-fatal): %s", e)
        return None
    finally:
        try:
            cursor.close()
        except Exception:
            pass


def store_generate_request(
    user_email: str,
    task_type: str,
    columns: list,
    prompt: str,
    num_rows: int,
    status: str = "completed",
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """Log a generation request. Silently skips if DB is unavailable."""
    conn = get_db_connection()
    if conn is None:
        logger.debug("DB unavailable — skipping request log for %s", user_email)
        return
    try:
        user_id = user_id_for_email(conn, user_email)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO synthetic_requests
               (user_id, task_type, prompt, columns, num_rows, status, error, duration_ms)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, task_type, prompt, json.dumps(columns), num_rows, status, error, duration_ms),
        )
        conn.commit()
    except Exception as e:
        logger.warning("store_generate_request failed (non-fatal): %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
