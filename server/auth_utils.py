from functools import wraps
from flask import request, jsonify
import jwt
import os

class InvalidTokenError(Exception):
    pass

def valid_api_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != os.getenv('API_KEY', 'default_key'):
            return jsonify({"error": "Invalid API key"}), 401
        return f(*args, **kwargs)
    return decorated_function

def extractUserEmailFromRequest(request):
    """Extract user email from JWT token in Authorization header"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise InvalidTokenError("No valid Authorization header")
    
    token = auth_header.split(' ')[1]
    try:
        # Decode JWT token (you may need to adjust the secret key)
        payload = jwt.decode(token, os.getenv('JWT_SECRET', 'your-secret-key'), algorithms=['HS256'])
        user_email = payload.get('email')
        if not user_email:
            raise InvalidTokenError("No email in token")
        return user_email
    except jwt.InvalidTokenError:
        raise InvalidTokenError("Invalid JWT token") 