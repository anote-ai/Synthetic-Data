"""
Example input/output tests demonstrating the API contract.
These serve as documentation as well as regression tests.
"""
import pytest
from unittest.mock import patch


EXAMPLE_TEXT_RESPONSE = {
    "data": [
        {"question": "What is Python?", "answer": "A high-level, interpreted programming language.", "status": "succeeded"},
        {"question": "What is a decorator?", "answer": "A function that wraps another function to extend behavior.", "status": "succeeded"},
        {"question": "What is a generator?", "answer": "A function that yields values lazily using the yield keyword.", "status": "succeeded"},
    ]
}

EXAMPLE_IMAGE_RESPONSE = {
    "data": [
        {
            "image_path": "outputs/images/image_0.png",
            "image_url": "https://oaidalleapiprodscus.blob.core.windows.net/...",
            "image_base64": "<base64 encoded PNG>",
            "revised_prompt": "A serene beach scene...",
            "size": "1024x1024",
            "style": "vivid",
            "detections": [
                {"label": "umbrella", "confidence": 0.91, "bbox": [120.0, 200.0, 400.0, 500.0]},
                {"label": "person", "confidence": 0.88, "bbox": [50.0, 100.0, 200.0, 600.0]},
            ],
            "detected_image_path": "outputs/images/detected_image_0.png",
            "status": "succeeded",
        }
    ]
}

EXAMPLE_AUDIO_RESPONSE = {
    "data": [
        {
            "audio_path": "outputs/audio/audio_0.mp3",
            "audio_base64": "<base64 encoded MP3>",
            "script": "Hello, thank you for calling TechSupport. How can I help you today?",
            "transcript": "Hello, thank you for calling TechSupport. How can I help you today?",
            "segments": [
                {"start": 0.0, "end": 1.2, "text": "Hello, thank you for calling TechSupport."},
                {"start": 1.2, "end": 2.5, "text": "How can I help you today?"},
            ],
            "language": "en",
            "voice": "nova",
            "tts_model": "tts-1",
            "status": "succeeded",
        }
    ]
}

EXAMPLE_VIDEO_RESPONSE = {
    "data": [
        {
            "video_path": "outputs/video/video_0.mp4",
            "video_url": "https://replicate.delivery/pbxt/...",
            "video_base64": "<base64 encoded MP4>",
            "duration_seconds": 4.0,
            "fps": 6,
            "resolution": "576x320",
            "prediction_id": "abc123",
            "frame_annotations": [
                {"frame_index": 0, "timestamp": 0.0, "description": "A city skyline at dusk with glowing lights."},
                {"frame_index": 12, "timestamp": 2.0, "description": "Traffic flowing through downtown streets."},
            ],
            "status": "succeeded",
        }
    ]
}

EXAMPLE_AGENT_RESPONSE = {
    "data": [
        {
            "task": "I need to reset my password",
            "tools_available": ["lookup_account", "reset_password", "escalate_ticket"],
            "turns": [
                {"role": "user", "content": "I need to reset my password"},
                {"role": "assistant", "content": None, "tool_calls": [{"name": "lookup_account", "args": {"email": "user@example.com"}}]},
                {"role": "tool", "tool_name": "lookup_account", "content": '{"account_id": "U123", "status": "active"}'},
                {"role": "assistant", "content": None, "tool_calls": [{"name": "reset_password", "args": {"account_id": "U123"}}]},
                {"role": "tool", "tool_name": "reset_password", "content": '{"success": true, "email_sent": true}'},
                {"role": "assistant", "content": "I've sent a password reset email to your registered address."},
            ],
            "outcome": "success",
            "num_tool_calls": 2,
            "resolution": "Password reset email sent successfully",
            "status": "succeeded",
        }
    ]
}


class TestExampleTextRequest:
    """Verify the text generation API contract with example inputs/outputs."""

    def test_python_qa_generation(self, client):
        payload = {
            "task_type": "text",
            "prompt": "Generate Q&A pairs about Python programming",
            "num_rows": 3,
            "columns": ["question", "answer"],
            "examples": [{"question": "What is a list?", "answer": "An ordered collection"}],
        }
        with patch("generators.text.generate_text_data", return_value=EXAMPLE_TEXT_RESPONSE["data"]):
            resp = client.post("/public/generate", json=payload)
        assert resp.status_code == 200
        result = resp.get_json()
        assert result == EXAMPLE_TEXT_RESPONSE

    def test_sentiment_dataset_generation(self, client):
        payload = {
            "task_type": "text",
            "prompt": "Generate product reviews with sentiment labels",
            "num_rows": 2,
            "columns": ["review_text", "sentiment", "rating"],
        }
        mock_data = [
            {"review_text": "Great product!", "sentiment": "positive", "rating": "5", "status": "succeeded"},
            {"review_text": "Terrible experience.", "sentiment": "negative", "rating": "1", "status": "succeeded"},
        ]
        with patch("generators.text.generate_text_data", return_value=mock_data):
            resp = client.post("/public/generate", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data) == 2
        assert all("sentiment" in row for row in data)


class TestExampleImageRequest:
    """Verify the image generation API contract."""

    def test_beach_image_with_detection(self, client):
        payload = {
            "task_type": "image",
            "prompt": "A sunny beach with palm trees and people",
            "num_rows": 1,
            "columns": ["image_path", "image_url", "detections"],
            "params": {"image_size": "1024x1024", "style": "vivid", "run_detection": True},
        }
        with patch("generators.image.generate_image_data", return_value=EXAMPLE_IMAGE_RESPONSE["data"]):
            resp = client.post("/public/generate", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()["data"][0]
        assert data["status"] == "succeeded"
        assert isinstance(data["detections"], list)


class TestExampleAudioRequest:
    """Verify the audio generation API contract."""

    def test_customer_support_audio(self, client):
        payload = {
            "task_type": "audio",
            "prompt": "Customer support calls for a software company",
            "num_rows": 1,
            "columns": ["transcript", "language", "voice"],
            "params": {"voice": "nova"},
        }
        with patch("generators.audio.generate_audio_data", return_value=EXAMPLE_AUDIO_RESPONSE["data"]):
            resp = client.post("/public/generate", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()["data"][0]
        assert "transcript" in data
        assert data["language"] == "en"


class TestExampleVideoRequest:
    """Verify the video generation API contract."""

    def test_city_timelapse_video(self, client):
        payload = {
            "task_type": "video",
            "prompt": "A time-lapse of a city at night",
            "num_rows": 1,
            "columns": ["video_path", "video_url", "duration_seconds", "frame_annotations"],
            "params": {"annotate_frames": True, "num_keyframes": 5},
        }
        with patch("generators.video.generate_video_data", return_value=EXAMPLE_VIDEO_RESPONSE["data"]):
            resp = client.post("/public/generate", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()["data"][0]
        assert data["status"] == "succeeded"
        assert "frame_annotations" in data


class TestExampleAgentRequest:
    """Verify the agent trace generation API contract."""

    def test_customer_support_agent_trace(self, client):
        payload = {
            "task_type": "agent",
            "prompt": "Customer support agent for a SaaS product",
            "num_rows": 1,
            "columns": ["task", "turns", "outcome", "num_tool_calls"],
            "params": {
                "scenario": "Password reset support",
                "tools": [
                    {"name": "lookup_account", "description": "Look up user account", "parameters": {"email": "string"}},
                    {"name": "reset_password", "description": "Send password reset", "parameters": {"account_id": "string"}},
                ],
                "difficulty": "easy",
            },
        }
        with patch("generators.agent.generate_agent_data", return_value=EXAMPLE_AGENT_RESPONSE["data"]):
            resp = client.post("/public/generate", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()["data"][0]
        assert data["status"] == "succeeded"
        assert isinstance(data["turns"], list)
        assert len(data["turns"]) > 0
        assert all("role" in t for t in data["turns"])
