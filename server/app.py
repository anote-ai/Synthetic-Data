from flask import Flask, request, jsonify, send_file
from auth_utils import valid_api_key_required, extractUserEmailFromRequest, InvalidTokenError
from api_endpoints.handler import GenerateHandler
from database.db import init_database
import os

app = Flask(__name__)

# Initialize database on startup
init_database()

@app.route('/public/generate', methods=['POST'])
# @valid_api_key_required  # Uncomment if using API key check
def generate():
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError:
        # For testing purposes, use a default email if JWT is missing
        user_email = "test@example.com"
        print("Warning: Using default email for testing")

    return GenerateHandler(request, user_email)

@app.route('/public/download/<file_id>', methods=['GET'])
def download(file_id):
    file_path = os.path.join("output_files", f"{file_id}.json")
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, as_attachment=True, download_name=f"{file_id}.json")

if __name__ == "__main__":
    app.run(debug=True)
