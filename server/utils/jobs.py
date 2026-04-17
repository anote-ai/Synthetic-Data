"""
Async job queue — file-based store with optional Redis/RQ backend.

Job lifecycle: queued → running → succeeded | failed
Jobs auto-expire after JOB_TTL_HOURS via the cleanup endpoint or on list.
"""
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_JOBS_DIR = Path(os.getenv("SYNTHETIC_OUTPUT_DIR", "./outputs")) / "jobs"
JOB_TTL_HOURS = int(os.getenv("JOB_TTL_HOURS", "24"))


def _jobs_dir() -> Path:
    _JOBS_DIR.mkdir(parents=True, exist_ok=True)
    return _JOBS_DIR


# ── Job persistence ───────────────────────────────────────────────────────────

def _write(job: dict) -> None:
    path = _jobs_dir() / f"{job['job_id']}.json"
    path.write_text(json.dumps(job, ensure_ascii=False, indent=2))


def _read(job_id: str) -> Optional[dict]:
    path = _jobs_dir() / f"{job_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def create_job(task_type: str, user_email: str, body: dict) -> dict:
    job = {
        "job_id": str(uuid.uuid4()),
        "status": "queued",
        "task_type": task_type,
        "user_email": user_email,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "progress": {"completed": 0, "total": body.get("num_rows", 5)},
        "result": None,
        "error": None,
        "webhook_url": body.get("webhook_url"),
    }
    _write(job)
    return job


def get_job(job_id: str) -> Optional[dict]:
    return _read(job_id)


def update_job(job_id: str, **kwargs) -> Optional[dict]:
    job = _read(job_id)
    if job is None:
        return None
    job.update(kwargs)
    job["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _write(job)
    return job


def cancel_job(job_id: str) -> Optional[dict]:
    job = _read(job_id)
    if job is None:
        return None
    if job["status"] in ("queued", "running"):
        return update_job(job_id, status="canceled")
    return job


# ── Webhook delivery ──────────────────────────────────────────────────────────

def _send_webhook(job: dict) -> None:
    webhook_url = job.get("webhook_url")
    if not webhook_url:
        return
    try:
        import httpx
        payload = json.dumps({
            "job_id": job["job_id"],
            "status": job["status"],
            "data": job.get("result"),
        }).encode()
        headers = {"Content-Type": "application/json"}
        secret = os.getenv("WEBHOOK_SECRET", "")
        if secret:
            sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
            headers["X-Signature-SHA256"] = f"sha256={sig}"
        httpx.post(webhook_url, content=payload, headers=headers, timeout=10)
    except Exception as e:
        logger.warning("Webhook delivery failed for job %s: %s", job["job_id"], e)


# ── In-process threaded worker (fallback when Redis unavailable) ──────────────

def _run_job_in_thread(job_id: str, body: dict, user_email: str) -> None:
    from api_endpoints.handler import _resolve_generator
    update_job(job_id, status="running")
    try:
        task_type = body.get("task_type")
        generator_fn = _resolve_generator(task_type)
        if generator_fn is None:
            raise ValueError(f"Unsupported task_type: {task_type}")

        rows = generator_fn(
            body.get("prompt", ""),
            body.get("columns", []),
            body.get("num_rows", 5),
            body.get("examples", []),
            body.get("params", {}),
        )
        update_job(job_id, status="succeeded", result=rows, progress={"completed": len(rows), "total": len(rows)})
        job = get_job(job_id)
        if job:
            _send_webhook(job)
    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e, exc_info=True)
        update_job(job_id, status="failed", error=str(e))
        job = get_job(job_id)
        if job:
            _send_webhook(job)


def submit_job(body: dict, user_email: str) -> dict:
    """
    Submit a generation job. Uses RQ if REDIS_URL is set; otherwise threads.
    Returns the job dict with job_id and initial status='queued'.
    """
    job = create_job(body.get("task_type", ""), user_email, body)
    job_id = job["job_id"]

    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            from redis import Redis
            from rq import Queue as RQueue
            conn = Redis.from_url(redis_url)
            q = RQueue(connection=conn)
            q.enqueue(_run_job_in_thread, job_id, body, user_email, job_timeout=1800)
            return job
        except Exception as e:
            logger.warning("RQ enqueue failed (%s); falling back to thread", e)

    t = threading.Thread(target=_run_job_in_thread, args=(job_id, body, user_email), daemon=True)
    t.start()
    return job
