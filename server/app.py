import logging
import time
import uuid

from flask import Flask, request, jsonify, g
from auth_utils import valid_api_key_required, extractUserEmailFromRequest, InvalidTokenError
from api_endpoints.handler import GenerateHandler
from logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.before_request
def attach_request_id():
    g.request_id = str(uuid.uuid4())
    g.start_time = time.time()


@app.after_request
def log_request(response):
    duration_ms = int((time.time() - getattr(g, 'start_time', time.time())) * 1000)
    response.headers['X-Request-ID'] = getattr(g, 'request_id', '')
    logger.info(
        "Request completed",
        extra={
            "request_id": getattr(g, 'request_id', ''),
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
    )
    return response


@app.route('/public/generate', methods=['POST'])
# @valid_api_key_required
def generate():
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError:
        return jsonify({"error": "Invalid JWT"}), 401
    return GenerateHandler(request, user_email)


@app.route('/public/generate/export', methods=['POST'])
# @valid_api_key_required
def generate_export():
    """Generate data and return as downloadable file."""
    from utils.export import make_export_response

    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    body = request.get_json()
    fmt = body.pop("format", "json")
    filename = body.pop("filename", "synthetic_data")

    VALID_FORMATS = {"csv", "jsonl", "parquet", "json"}
    if fmt not in VALID_FORMATS:
        return jsonify({"error": f"Invalid format '{fmt}'. Must be one of: {VALID_FORMATS}"}), 422

    # Build a mock request object so GenerateHandler can parse it
    class _BodyRequest:
        def __init__(self, body):
            self.json = body

    result = GenerateHandler(_BodyRequest(body), user_email)
    # GenerateHandler returns a Flask Response via jsonify
    data = result.get_json().get("data", [])

    try:
        return make_export_response(data, fmt, filename)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
