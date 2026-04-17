import logging
import os
import time
import uuid

from flask import Flask, request, jsonify, g, Response, stream_with_context
from flask_cors import CORS
from auth_utils import valid_api_key_required, extractUserEmailFromRequest, InvalidTokenError
from api_endpoints.handler import GenerateHandler
from logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(
    app,
    origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

VALID_TASK_TYPES = {"text", "image", "video", "audio", "agent", "pii", "language", "tabular", "code"}
MAX_ROWS = int(os.getenv("MAX_ROWS_PER_REQUEST", "100"))


@app.before_request
def attach_request_id():
    g.request_id = str(uuid.uuid4())
    g.start_time = time.time()


@app.after_request
def log_request(response):
    duration_ms = int((time.time() - getattr(g, "start_time", time.time())) * 1000)
    response.headers["X-Request-ID"] = getattr(g, "request_id", "")
    logger.info(
        "Request completed",
        extra={
            "request_id": getattr(g, "request_id", ""),
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/public/generate", methods=["POST"])
def generate():
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    body = request.get_json(silent=True) or {}

    # Inline validation — keeps 422 responses consistent
    errors = {}
    task_type = body.get("task_type")
    if not task_type:
        errors["task_type"] = "field required"
    elif task_type not in VALID_TASK_TYPES:
        errors["task_type"] = f"must be one of {sorted(VALID_TASK_TYPES)}"

    if not body.get("prompt", "").strip():
        errors["prompt"] = "field required"

    columns = body.get("columns", [])
    if not columns:
        errors["columns"] = "must be a non-empty list"

    num_rows = body.get("num_rows", 5)
    if not isinstance(num_rows, int) or num_rows < 1 or num_rows > MAX_ROWS:
        errors["num_rows"] = f"must be an integer between 1 and {MAX_ROWS}"

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    result = GenerateHandler(request, user_email)

    # Save version snapshot (non-fatal if it fails)
    try:
        from utils.versioning import save_version
        generated_data = result.get_json().get("data", [])
        version_id = save_version(
            user_email=user_email,
            task_type=body.get("task_type"),
            prompt=body.get("prompt", ""),
            columns=body.get("columns", []),
            params=body.get("params", {}),
            result_data=generated_data,
            num_rows=body.get("num_rows", 5),
        )
        payload = result.get_json()
        payload["version_id"] = version_id
        return jsonify(payload)
    except Exception as e:
        logger.warning("Versioning failed (non-fatal): %s", e)
        return result


@app.route("/public/generate/versions", methods=["GET"])
def list_versions():
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    limit = min(int(request.args.get("limit", 20)), 100)
    from utils.versioning import list_versions as _list
    return jsonify({"versions": _list(user_email, limit)})


@app.route("/public/generate/versions/<version_id>", methods=["GET"])
def get_version(version_id):
    try:
        extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    from utils.versioning import get_version as _get
    record = _get(version_id)
    if record is None:
        return jsonify({"error": f"Version '{version_id}' not found"}), 404
    return jsonify(record)


@app.route("/public/generate/export", methods=["POST"])
def generate_export():
    from utils.export import make_export_response

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    body = request.get_json() or {}
    fmt = body.pop("format", "json")
    filename = body.pop("filename", "synthetic_data")

    VALID_FORMATS = {"csv", "jsonl", "parquet", "json"}
    if fmt not in VALID_FORMATS:
        return jsonify({"error": f"Invalid format. Must be one of: {VALID_FORMATS}"}), 422

    class _BodyRequest:
        def __init__(self, b):
            self.json = b
            self.is_json = True
            self.headers = request.headers

    result = GenerateHandler(_BodyRequest(body), user_email)
    data = result.get_json().get("data", [])

    try:
        return make_export_response(data, fmt, filename)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/public/generate/quality", methods=["POST"])
def generate_quality():
    from utils.quality import score_dataset

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    body = request.get_json() or {}
    data = body.get("data", [])
    prompt = body.get("prompt", "")
    run_llm_review = body.get("run_llm_review", False)
    deduplicate = body.get("deduplicate", False)

    if not isinstance(data, list) or not data:
        return jsonify({"error": "data must be a non-empty list"}), 422

    try:
        report = score_dataset(data, prompt=prompt, run_llm_review=run_llm_review)
    except Exception as e:
        logger.error("Quality scoring failed: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500

    response = {"quality": report}
    if deduplicate:
        from utils.quality import deduplicate as dedup_fn
        response["data"] = dedup_fn(data)
    return jsonify(response)


@app.route("/public/generate/stream", methods=["POST"])
def generate_stream():
    """
    SSE endpoint — streams rows one-by-one as they are generated.

    Same request body as POST /public/generate.
    Response: text/event-stream with one 'data: <json>' line per row,
    ending with {"type": "done", "total_rows": N}.
    """
    import json as _json
    from api_endpoints.handler import _resolve_generator

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    body = request.get_json(silent=True) or {}
    task_type = body.get("task_type")
    prompt = body.get("prompt", "")
    num_rows = body.get("num_rows", 5)
    columns = body.get("columns", [])
    examples = body.get("examples", [])
    params = body.get("params", {})

    def event_stream():
        generator_fn = _resolve_generator(task_type)
        if generator_fn is None:
            yield f'data: {_json.dumps({"type": "error", "message": f"Unsupported task_type: {task_type}"})}\n\n'
            return
        try:
            rows = generator_fn(prompt, columns, num_rows, examples, params)
        except Exception as e:
            yield f'data: {_json.dumps({"type": "error", "message": str(e)})}\n\n'
            return
        for i, row in enumerate(rows):
            yield f'data: {_json.dumps({"type": "progress", "row": i, "total": len(rows), "data": row})}\n\n'
        yield f'data: {_json.dumps({"type": "done", "total_rows": len(rows)})}\n\n'

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/public/generate/async", methods=["POST"])
def generate_async():
    """Submit a generation job and return immediately with a job_id."""
    from utils.jobs import submit_job

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    body = request.get_json(silent=True) or {}

    errors = {}
    task_type = body.get("task_type")
    if not task_type:
        errors["task_type"] = "field required"
    elif task_type not in VALID_TASK_TYPES:
        errors["task_type"] = f"must be one of {sorted(VALID_TASK_TYPES)}"
    if not body.get("prompt", "").strip():
        errors["prompt"] = "field required"
    if not body.get("columns", []):
        errors["columns"] = "must be a non-empty list"
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    job = submit_job(body, user_email)
    return jsonify({"job_id": job["job_id"], "status": job["status"]}), 202


@app.route("/public/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    """Return job status and result (once complete)."""
    from utils.jobs import get_job as _get

    try:
        extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    job = _get(job_id)
    if job is None:
        return jsonify({"error": f"Job '{job_id}' not found"}), 404
    return jsonify(job)


@app.route("/public/jobs/<job_id>", methods=["DELETE"])
def cancel_job(job_id):
    """Cancel a queued or running job."""
    from utils.jobs import cancel_job as _cancel

    try:
        extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    job = _cancel(job_id)
    if job is None:
        return jsonify({"error": f"Job '{job_id}' not found"}), 404
    return jsonify(job)
