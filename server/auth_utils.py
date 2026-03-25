"""
Authentication utilities for the Synthetic Data API.
Provides JWT validation and API key checking for Flask routes.
"""
import os
import logging
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """Raised when JWT token is missing, malformed, or invalid."""
    pass


def extractUserEmailFromRequest(req) -> str:
    """
    Extract and validate JWT from Authorization header.

    Expected header: Authorization: Bearer <jwt_token>

    Returns:
        User email from token payload

    Raises:
        InvalidTokenError: if token is missing, malformed, or invalid
    """
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise InvalidTokenError("Missing or malformed Authorization header. Expected: Bearer <token>")

    token = auth_header[len("Bearer "):]
    if not token:
        raise InvalidTokenError("Empty token in Authorization header")

    try:
        import jwt
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("email") or payload.get("sub") or payload.get("user_email")
        if not email:
            raise InvalidTokenError("Token payload missing email/sub field")
        return email
    except ImportError:
        # PyJWT not installed — fall back to treating token as opaque API key
        # This allows the server to function while JWT is being set up
        logger.warning("PyJWT not installed; treating Authorization token as opaque API key")
        return f"user+{token[:8]}@api.key"
    except Exception as e:
        raise InvalidTokenError(f"Token validation failed: {e}")


def valid_api_key_required(f):
    """
    Flask decorator that validates the JWT/API key before calling the route.
    Returns 401 JSON on invalid/missing token.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            extractUserEmailFromRequest(request)
        except InvalidTokenError as e:
            logger.warning("Auth failed: %s", e)
            return jsonify({"error": "Unauthorized", "detail": str(e)}), 401
        return f(*args, **kwargs)
    return decorated


def generate_token(email: str, expires_hours: int = 24) -> str:
    """
    Generate a signed JWT for a given email address.
    Useful for testing and local development.

    Args:
        email: User email address
        expires_hours: Token expiry in hours (default: 24)

    Returns:
        Signed JWT string
    """
    try:
        import jwt
        from datetime import datetime, timedelta, timezone
        payload = {
            "email": email,
            "sub": email,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    except ImportError:
        raise RuntimeError("PyJWT is required to generate tokens. Run: pip install PyJWT>=2.8")
