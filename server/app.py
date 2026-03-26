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

    body = request.json or {}
    seed = body.get("seed")
    result = GenerateHandler(request, user_email)

    # Save a versioned snapshot after successful generation
    if hasattr(result, "get_json"):
        result_data = result.get_json() or {}
        data_rows = result_data.get("data", [])
        if data_rows:
            from database.db import save_version
            version_id = save_version(
                user_email=user_email,
                task_type=body.get("task_type"),
                prompt=body.get("prompt"),
                columns=body.get("columns", []),
                num_rows=body.get("num_rows", len(data_rows)),
                params=body.get("params", {}),
                seed=seed,
                result_data=data_rows,
            )
            result_data["version_id"] = version_id
            return jsonify(result_data)
    return result


@app.route('/public/generate/versions', methods=['GET'])
@valid_api_key_required
def list_versions():
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError:
        return jsonify({"error": "Invalid JWT"}), 401
    from database.db import list_versions as _list
    limit = min(int(request.args.get("limit", 20)), 100)
    return jsonify({"versions": _list(user_email, limit=limit)})


@app.route('/public/generate/versions/<version_id>', methods=['GET'])
@valid_api_key_required
def get_version(version_id):
    try:
        extractUserEmailFromRequest(request)
    except InvalidTokenError:
        return jsonify({"error": "Invalid JWT"}), 401
    from database.db import get_version as _get
    version = _get(version_id)
    if not version:
        return jsonify({"error": "Version not found"}), 404
    return jsonify(version)
