"""
Dataset versioning — stores generation snapshots as JSON files.
Falls back gracefully when DB is unavailable; always returns a version_id.
"""
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_VERSIONS_DIR = Path(os.getenv("SYNTHETIC_OUTPUT_DIR", "./outputs")) / "versions"


def _versions_dir() -> Path:
    d = _VERSIONS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_version(
    user_email: str,
    task_type: str,
    prompt: str,
    columns: list,
    params: dict,
    result_data: list,
    num_rows: int,
) -> str:
    """
    Persist a generation snapshot and return a UUID version_id.
    Never raises — on failure logs a warning and still returns a UUID.
    """
    version_id = str(uuid.uuid4())
    record = {
        "version_id": version_id,
        "user_email": user_email,
        "task_type": task_type,
        "prompt": prompt,
        "columns": columns,
        "params": params,
        "num_rows": num_rows,
        "row_count": len(result_data),
        "status": "completed",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "result_data": result_data,
    }
    try:
        path = _versions_dir() / f"{version_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.warning("Could not persist version %s: %s", version_id, e)

    # Also try DB if available
    try:
        from database.db import get_db_connection
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO generation_versions
                   (version_id, user_email, task_type, prompt, columns, params,
                    result_data, row_count, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    version_id, user_email, task_type, prompt,
                    json.dumps(columns), json.dumps(params),
                    json.dumps(result_data), len(result_data), "completed",
                ),
            )
            conn.commit()
            conn.close()
    except Exception:
        pass  # DB optional — file store is the fallback

    return version_id


def get_version(version_id: str) -> Optional[dict]:
    """Return the full version record, or None if not found."""
    # Try file store first
    try:
        path = _versions_dir() / f"{version_id}.json"
        if path.exists():
            return json.loads(path.read_text())
    except Exception as e:
        logger.warning("Could not read version file %s: %s", version_id, e)

    # Try DB fallback
    try:
        from database.db import get_db_connection
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM generation_versions WHERE version_id = %s", (version_id,)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                for field in ("columns", "params", "result_data"):
                    if isinstance(row.get(field), str):
                        row[field] = json.loads(row[field])
                return row
    except Exception:
        pass

    return None


def list_versions(user_email: str, limit: int = 20) -> list:
    """Return recent version metadata (without result_data) for a user."""
    versions = []
    try:
        d = _versions_dir()
        files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files:
            try:
                record = json.loads(f.read_text())
                if record.get("user_email") == user_email:
                    versions.append({k: v for k, v in record.items() if k != "result_data"})
                    if len(versions) >= limit:
                        break
            except Exception:
                continue
    except Exception as e:
        logger.warning("Could not list versions: %s", e)
    return versions
