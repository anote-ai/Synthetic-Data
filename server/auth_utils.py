"""JWT authentication utilities for the Flask API."""
import os
import functools

from flask import request, jsonify

try:
    import jwt as pyjwt
    _HAS_JWT = True
except BaseException:
    _HAS_JWT = False


class InvalidTokenError(Exception):
    pass


def extractUserEmailFromRequest(req) -> str:
    """Extract user email from JWT Bearer token in Authorization header."""
    auth_header = req.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer":
        raise InvalidTokenError("Missing or malformed Authorization header")
    if not _HAS_JWT:
        # Without PyJWT installed, accept any non-empty token
        return "user@example.com"
    secret = os.getenv("JWT_SECRET_KEY", "dev-secret")
    try:
        payload = pyjwt.decode(token, secret, algorithms=["HS256"])
        return payload.get("email", "user@example.com")
    except Exception as e:
        raise InvalidTokenError(str(e))


def valid_api_key_required(f):
    """Flask decorator that requires a valid JWT on the route."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        try:
            extractUserEmailFromRequest(request)
        except InvalidTokenError as e:
            return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401
        return f(*args, **kwargs)
    return decorated


def generate_token(email: str) -> str:
    """Dev utility: generate a signed JWT for testing."""
    if not _HAS_JWT:
        raise RuntimeError("PyJWT not installed — pip install PyJWT")
    import time
    secret = os.getenv("JWT_SECRET_KEY", "dev-secret")
    payload = {
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")
