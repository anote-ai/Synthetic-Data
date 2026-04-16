"""Shared pytest fixtures for Synthetic Data API tests."""
import pytest
import os
import sys

# Ensure server/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set dummy env vars before imports so modules don't crash on load
os.environ.setdefault("OPENAI_API_KEY", "test-key-sk-1234")
os.environ.setdefault("REPLICATE_API_TOKEN", "test-replicate-token")
os.environ.setdefault("SYNTHETIC_OUTPUT_DIR", "/tmp/synthetic-test-output")


@pytest.fixture
def app():
    """Flask test app with test config."""
    # Patch auth before importing app
    import unittest.mock as mock
    with mock.patch("auth_utils.valid_api_key_required", lambda f: f), \
         mock.patch("auth_utils.extractUserEmailFromRequest", return_value="test@example.com"):
        from app import app as flask_app
        flask_app.config["TESTING"] = True
        yield flask_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def valid_text_payload():
    return {
        "task_type": "text",
        "prompt": "Generate Q&A pairs about Python programming",
        "num_rows": 3,
        "columns": ["question", "answer"],
        "examples": [{"question": "What is a list?", "answer": "An ordered collection"}],
        "params": {},
    }


@pytest.fixture
def valid_image_payload():
    return {
        "task_type": "image",
        "prompt": "A sunny beach with palm trees",
        "num_rows": 1,
        "columns": ["image_path", "image_url", "detections"],
        "examples": [],
        "params": {"image_size": "1024x1024", "style": "vivid", "run_detection": False},
    }


@pytest.fixture
def valid_audio_payload():
    return {
        "task_type": "audio",
        "prompt": "Customer support call for a software product",
        "num_rows": 1,
        "columns": ["transcript", "sentiment", "language"],
        "examples": [],
        "params": {"voice": "nova", "tts_model": "tts-1"},
    }


@pytest.fixture
def valid_video_payload():
    return {
        "task_type": "video",
        "prompt": "A time-lapse of a city at night",
        "num_rows": 1,
        "columns": ["video_path", "video_url", "duration_seconds"],
        "examples": [],
        "params": {"annotate_frames": False},
    }


@pytest.fixture
def valid_agent_payload():
    return {
        "task_type": "agent",
        "prompt": "Customer support agent for a SaaS product",
        "num_rows": 2,
        "columns": ["task", "turns", "outcome", "num_tool_calls"],
        "examples": [],
        "params": {
            "scenario": "Customer support for billing issues",
            "difficulty": "medium",
            "tools": [
                {"name": "lookup_account", "description": "Look up account by email", "parameters": {"email": "string"}},
                {"name": "process_refund", "description": "Process a refund", "parameters": {"account_id": "string", "amount": "number"}},
            ],
        },
    }
