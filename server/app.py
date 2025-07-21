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
