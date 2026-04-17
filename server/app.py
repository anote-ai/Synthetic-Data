import logging
import os
import time
import uuid

from flask import Flask, request, jsonify, g
from auth_utils import valid_api_key_required, extractUserEmailFromRequest, InvalidTokenError
from api_endpoints.handler import GenerateHandler
from logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

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

    return GenerateHandler(request, user_email)


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
