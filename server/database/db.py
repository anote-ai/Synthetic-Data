import os
import json
import uuid
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

_pool = None


def get_db_connection():
    """Return a MySQL connection from the pool, or None if DB is not configured."""
    global _pool
    host = os.getenv("DB_HOST")
    if not host:
        return None
    try:
        if _pool is None:
            import mysql.connector.pooling as pooling
            _pool = pooling.MySQLConnectionPool(
                pool_name="synth_pool",
                pool_size=5,
                host=host,
                port=int(os.getenv("DB_PORT", 3306)),
                database=os.getenv("DB_NAME", "synthetic_data"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
            )
        return _pool.get_connection()
    except Exception as e:
        logger.warning("DB connection failed: %s", e)
        return None


def store_generate_request(user_email, task_type, columns, prompt, num_rows):
    conn = get_db_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO synthetic_requests (user_id, task_type, prompt, columns, num_rows) VALUES (%s, %s, %s, %s, %s)',
            [0, task_type, prompt, json.dumps(columns), num_rows]
        )
        conn.commit()
    except Exception as e:
        logger.warning("store_generate_request failed: %s", e)
    finally:
        conn.close()


def save_version(user_email, task_type, prompt, columns, num_rows, params, seed, result_data) -> Optional[str]:
    """Save a generation result as a versioned snapshot. Returns version_id UUID."""
    conn = get_db_connection()
    version_id = str(uuid.uuid4())
    if conn is None:
        return version_id  # still return an ID even without DB
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO generation_versions
               (version_id, user_email, task_type, prompt, columns, num_rows, params, seed, result_data, row_count)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [
                version_id, user_email, task_type, prompt,
                json.dumps(columns), num_rows, json.dumps(params or {}),
                seed, json.dumps(result_data), len(result_data),
            ]
        )
        conn.commit()
    except Exception as e:
        logger.warning("save_version failed: %s", e)
    finally:
        conn.close()
    return version_id


def get_version(version_id) -> Optional[dict]:
    """Fetch a single version by ID."""
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM generation_versions WHERE version_id = %s", [version_id])
        row = cursor.fetchone()
        if row:
            row["result_data"] = json.loads(row["result_data"] or "[]")
            row["columns"] = json.loads(row["columns"] or "[]")
            row["params"] = json.loads(row["params"] or "{}")
        return row
    except Exception as e:
        logger.warning("get_version failed: %s", e)
        return None
    finally:
        conn.close()


def list_versions(user_email, limit=20) -> List[dict]:
    """List recent versions for a user (excludes result_data for brevity)."""
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT version_id, user_email, task_type, prompt, num_rows, row_count, status, created_at
               FROM generation_versions WHERE user_email = %s
               ORDER BY created_at DESC LIMIT %s""",
            [user_email, limit]
        )
        return cursor.fetchall() or []
    except Exception as e:
        logger.warning("list_versions failed: %s", e)
        return []
    finally:
        conn.close()
