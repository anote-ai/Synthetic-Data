from functools import wraps
from flask import request, jsonify
import jwt
import os

class InvalidTokenError(Exception):
    pass

def extractUserEmailFromRequest(request):
    """Extract user email from JWT token in request headers"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise InvalidTokenError("No valid authorization header")
    
    token = auth_header.split(' ')[1]
    try:
        # For now, we'll use a simple approach - in production you'd verify the token
        # This is a placeholder implementation
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get('email', 'unknown@example.com')
    except jwt.InvalidTokenError:
        raise InvalidTokenError("Invalid JWT token")

def valid_api_key_required(f):
    """Decorator to validate API key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({"error": "API key required"}), 401
        # Add your API key validation logic here
        return f(*args, **kwargs)
    return decorated_function 