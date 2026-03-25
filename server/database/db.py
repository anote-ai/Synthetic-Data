"""
Database helper functions for the Synthetic Data API.
Gracefully degrades (logs warning, skips) when DB is unavailable.
"""
import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Check if DB is configured
_DB_CONFIGURED = all([
    os.getenv("DB_HOST"),
    os.getenv("DB_USER"),
    os.getenv("DB_PASSWORD"),
    os.getenv("DB_NAME"),
])

_pool = None


def _get_pool():
    """Lazily create a MySQL connection pool."""
    global _pool
    if _pool is not None:
        return _pool
    try:
        import mysql.connector.pooling
        _pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="synthetic_data",
            pool_size=5,
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
        )
        logger.info("Database connection pool created")
        return _pool
    except Exception as e:
        logger.warning("Failed to create DB connection pool: %s. DB logging disabled.", e)
        return None


def get_db_connection():
    """Get a connection from the pool. Returns None if DB unavailable."""
    if not _DB_CONFIGURED:
        return None
    pool = _get_pool()
    if pool is None:
        return None
    try:
        return pool.get_connection()
    except Exception as e:
        logger.warning("Failed to get DB connection: %s", e)
        return None


def user_id_for_email(conn, email: str) -> Optional[int]:
    """Upsert user by email, return user id."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (email) VALUES (%s) ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)",
            (email,)
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.warning("Failed to upsert user %s: %s", email, e)
        return None
    finally:
        cursor.close()


def store_generate_request(
    user_email: str,
    task_type: str,
    columns: list,
    prompt: str,
    num_rows: int,
    status: str = "completed",
    error: str = None,
    duration_ms: int = None,
) -> Optional[int]:
    """
    Log a generation request to the database.
    Returns inserted row id, or None if DB is unavailable.
    Failures are logged as warnings and never raise exceptions.
    """
    conn = get_db_connection()
    if conn is None:
        return None

    try:
        user_id = user_id_for_email(conn, user_email)
        if user_id is None:
            return None

        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO synthetic_requests
               (user_id, task_type, prompt, columns, num_rows, status, error, duration_ms)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, task_type, prompt, json.dumps(columns), num_rows, status, error, duration_ms)
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.warning("Failed to store generate request: %s", e)
        return None
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass
