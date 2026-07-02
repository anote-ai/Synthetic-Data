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
    name: Optional[str] = None,
    parent_version_id: Optional[str] = None,
    examples: Optional[list] = None,
) -> str:
    """
    Persist a generation snapshot and return a UUID version_id.
    Never raises — on failure logs a warning and still returns a UUID.
    """
    version_id = str(uuid.uuid4())
    examples = examples or []
    record = {
        "version_id": version_id,
        "user_email": user_email,
        "name": name,
        "parent_version_id": parent_version_id,
        "task_type": task_type,
        "prompt": prompt,
        "columns": columns,
        "examples": examples,
        "params": params,
        "num_rows": num_rows,
        "row_count": len(result_data),
        "quality_score": None,
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
                   (version_id, user_email, name, parent_version_id, task_type, prompt,
                    columns, examples, params, result_data, row_count, quality_score, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    version_id, user_email, name, parent_version_id, task_type, prompt,
                    json.dumps(columns), json.dumps(examples), json.dumps(params),
                    json.dumps(result_data), len(result_data), None, "completed",
                ),
            )
            conn.commit()
            conn.close()
    except Exception:
        pass  # DB optional — file store is the fallback

    return version_id


def update_version(version_id: str, **patch) -> Optional[dict]:
    """
    Patch mutable fields (name, quality_score) on an existing version.
    Returns the updated record, or None if the version doesn't exist.
    """
    allowed = {"name", "quality_score"}
    fields = {k: v for k, v in patch.items() if k in allowed}
    if not fields:
        return get_version(version_id)

    record = None
    try:
        path = _versions_dir() / f"{version_id}.json"
        if path.exists():
            record = json.loads(path.read_text())
            record.update(fields)
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.warning("Could not update version file %s: %s", version_id, e)

    try:
        from database.db import get_db_connection
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            set_clause = ", ".join(f"{k} = %s" for k in fields)
            values = [json.dumps(v) if k == "quality_score" else v for k, v in fields.items()]
            cursor.execute(
                f"UPDATE generation_versions SET {set_clause} WHERE version_id = %s",
                (*values, version_id),
            )
            conn.commit()
            conn.close()
    except Exception:
        pass

    return record if record is not None else get_version(version_id)


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


def diff_versions(version_id_a: str, version_id_b: str) -> Optional[dict]:
    """
    Compare two versions: metadata changes (prompt/columns/num_rows/params)
    plus a row-level diff (rows only in a, only in b, or in both).
    Returns None if either version doesn't exist.
    """
    a, b = get_version(version_id_a), get_version(version_id_b)
    if a is None or b is None:
        return None

    metadata_changes = {}
    for field in ("prompt", "columns", "num_rows", "params", "name"):
        if a.get(field) != b.get(field):
            metadata_changes[field] = {"from": a.get(field), "to": b.get(field)}

    rows_a = [json.dumps(r, sort_keys=True) for r in a.get("result_data", [])]
    rows_b = [json.dumps(r, sort_keys=True) for r in b.get("result_data", [])]
    set_a, set_b = set(rows_a), set(rows_b)

    return {
        "version_a": version_id_a,
        "version_b": version_id_b,
        "metadata_changes": metadata_changes,
        "row_count_a": len(rows_a),
        "row_count_b": len(rows_b),
        "rows_added": [json.loads(r) for r in set_b - set_a],
        "rows_removed": [json.loads(r) for r in set_a - set_b],
        "rows_unchanged": len(set_a & set_b),
    }
