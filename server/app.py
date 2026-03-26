import os
from flask import Flask, request, jsonify, Response, stream_with_context
from auth_utils import valid_api_key_required, extractUserEmailFromRequest, InvalidTokenError
from api_endpoints.handler import GenerateHandler, generate_streaming
from utils.quality import score_dataset, deduplicate

app = Flask(__name__)

@app.route('/public/generate', methods=['POST'])
# @valid_api_key_required
def generate():
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError:
        return jsonify({"error": "Invalid JWT"}), 401
    return GenerateHandler(request, user_email)

@app.route('/public/generate/stream', methods=['POST'])
@valid_api_key_required
def generate_stream():
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError:
        return jsonify({"error": "Invalid JWT"}), 401
    return Response(
        stream_with_context(generate_streaming(request, user_email)),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )

@app.route('/public/generate/quality', methods=['POST'])
@valid_api_key_required
def generate_quality():
    body = request.json or {}
    data = body.get("data", [])
    prompt = body.get("prompt", "")
    run_llm_review = body.get("run_llm_review", True)
    should_deduplicate = body.get("deduplicate", True)

    if not isinstance(data, list):
        return jsonify({"error": "\"data\" must be a list of row objects"}), 400

    quality_report = score_dataset(data, prompt, run_llm_review=run_llm_review)

    response_body = {"quality": quality_report}

    if should_deduplicate:
        deduped, _ = deduplicate(data)
        response_body["data"] = deduped

    return jsonify(response_body)
