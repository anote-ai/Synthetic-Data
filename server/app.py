from flask import Flask, request, jsonify
from flask_cors import CORS
from api_endpoints.handler import GenerateHandler

app = Flask(__name__)
CORS(app, resources={r"/public/*": {"origins": "http://localhost:3000"}})

@app.route('/public/generate', methods=['POST'])
def generate():
	# For local dev, skip auth and use a placeholder user email
	user_email = "local@dev"
	return GenerateHandler(request, user_email)

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5000, debug=True)
