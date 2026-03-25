from flask import Flask, request, jsonify
from dotenv import load_dotenv
from pydantic import ValidationError
import os

load_dotenv()

from auth_utils import valid_api_key_required, extractUserEmailFromRequest, InvalidTokenError
from api_endpoints.handler import GenerateHandler
from validators import GenerateRequest

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/public/generate', methods=['POST'])
@valid_api_key_required
def generate():
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError:
        return jsonify({"error": "Invalid JWT token"}), 401

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        payload = GenerateRequest(**request.get_json())
    except ValidationError as e:
        errors = [{"field": ".".join(str(x) for x in err["loc"]), "message": err["msg"]} for err in e.errors()]
        return jsonify({"error": "Validation failed", "details": errors}), 422
    except Exception as e:
        return jsonify({"error": f"Invalid request body: {str(e)}"}), 400

    return GenerateHandler(payload, user_email)

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true", port=int(os.getenv("PORT", 5000)))
