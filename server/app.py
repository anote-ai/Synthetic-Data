from flask import Flask, request, jsonify
from auth_utils import valid_api_key_required, extractUserEmailFromRequest, InvalidTokenError
from api_endpoints.handler import GenerateHandler

app = Flask(__name__)


@app.route('/public/generate', methods=['POST'])
# @valid_api_key_required
def generate():
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError:
        return jsonify({"error": "Invalid JWT"}), 401
    return GenerateHandler(request, user_email)


@app.route('/public/generate/quality', methods=['POST'])
@valid_api_key_required
def generate_quality():
    """Score quality of a dataset: dedup, completeness, LLM coherence review."""
    try:
        extractUserEmailFromRequest(request)
    except InvalidTokenError:
        return jsonify({"error": "Invalid JWT"}), 401

    body = request.json or {}
    data = body.get("data")
    if not data or not isinstance(data, list):
        return jsonify({"error": "data must be a non-empty list of row dicts"}), 400

    prompt = body.get("prompt", "")
    run_llm_review = body.get("run_llm_review", True)
    deduplicate_flag = body.get("deduplicate", False)

    from utils.quality import score_dataset, deduplicate
    report = score_dataset(data, prompt, run_llm_review=run_llm_review)

    response = {"quality": report}
    if deduplicate_flag:
        deduped, _ = deduplicate(data)
        response["data"] = deduped

    return jsonify(response)
