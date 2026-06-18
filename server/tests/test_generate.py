"""Tests for the /public/generate endpoint."""
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from types import SimpleNamespace


class TestHealthEndpoint:
    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"


class TestTaskTypesEndpoint:
    def test_task_types_are_discoverable(self, client):
        resp = client.get("/public/generate/task-types")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["task_types"] == [
            "agent",
            "audio",
            "code",
            "image",
            "language",
            "pii",
            "tabular",
            "text",
            "video",
        ]
        assert data["max_rows_per_request"] == 100


class TestValidation:
    def test_missing_task_type(self, client):
        resp = client.post("/public/generate", json={
            "prompt": "test", "num_rows": 1, "columns": ["col"]
        })
        assert resp.status_code == 422

    def test_invalid_task_type(self, client):
        resp = client.post("/public/generate", json={
            "task_type": "invalid", "prompt": "test", "num_rows": 1, "columns": ["col"]
        })
        assert resp.status_code == 422

    def test_empty_columns(self, client):
        resp = client.post("/public/generate", json={
            "task_type": "text", "prompt": "test", "num_rows": 1, "columns": []
        })
        assert resp.status_code == 422

    def test_num_rows_too_large(self, client):
        resp = client.post("/public/generate", json={
            "task_type": "text", "prompt": "test", "num_rows": 9999, "columns": ["col"]
        })
        assert resp.status_code == 422

    def test_non_json_body(self, client):
        resp = client.post("/public/generate", data="not json", content_type="text/plain")
        assert resp.status_code == 415

    def test_valid_request_accepted(self, client, valid_text_payload):
        mock_result = [{"question": "Q1", "answer": "A1", "status": "succeeded"}] * 3
        with patch("generators.text.generate_text_data", return_value=mock_result):
            resp = client.post("/public/generate", json=valid_text_payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data
        assert len(data["data"]) == 3


class TestTextGenerator:
    def test_generate_text_mocked(self, client, valid_text_payload):
        mock_result = [
            {"question": "What is Python?", "answer": "A programming language.", "status": "succeeded"},
            {"question": "What is a list?", "answer": "An ordered collection.", "status": "succeeded"},
            {"question": "What is a dict?", "answer": "A key-value store.", "status": "succeeded"},
        ]
        with patch("generators.text.generate_text_data", return_value=mock_result):
            resp = client.post("/public/generate", json=valid_text_payload)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data) == 3
        assert all(row["status"] == "succeeded" for row in data)
        assert all("question" in row and "answer" in row for row in data)

    def test_text_generator_returns_failed_on_error(self):
        """Test that text generator handles errors gracefully."""
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create = AsyncMock(side_effect=Exception("API error"))
            from generators.text import generate_text_data
            results = generate_text_data("test prompt", ["col1"], 1, [])
            assert all(r["status"] == "failed" for r in results)

    def test_text_generator_uses_json_object_mode(self):
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"question":"What is Python?","answer":"A language."}')
                )
            ]
        )
        create = AsyncMock(return_value=response)
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create = create
            from generators.text import generate_text_data
            results = generate_text_data(
                "Generate Q&A pairs",
                ["question", "answer"],
                1,
                [{"question": "What is a list?", "answer": "An ordered collection"}],
            )

        assert results == [{"question": "What is Python?", "answer": "A language.", "status": "succeeded"}]
        assert create.await_args.kwargs["response_format"] == {"type": "json_object"}

    def test_text_generator_retries_invalid_json(self):
        bad_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))])
        good_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"col1":"value"}'))])
        create = AsyncMock(side_effect=[bad_response, good_response])
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create = create
            from generators.text import generate_text_data
            results = generate_text_data("test prompt", ["col1"], 1, [])

        assert results == [{"col1": "value", "status": "succeeded"}]
        assert create.await_count == 2


class TestImageGenerator:
    def test_generate_image_mocked(self, client, valid_image_payload):
        mock_result = [{
            "image_path": "/tmp/image_0.png",
            "image_url": "https://example.com/image.png",
            "image_base64": "base64data",
            "status": "succeeded",
        }]
        with patch("generators.image.generate_image_data", return_value=mock_result):
            resp = client.post("/public/generate", json=valid_image_payload)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data[0]["status"] == "succeeded"
        assert "image_path" in data[0]

    def test_invalid_image_size(self):
        from generators.image import generate_image_data
        results = generate_image_data("test", ["image_path"], 1, [], {"image_size": "invalid_size"})
        assert results[0]["status"] == "failed"
        assert "image_size" in results[0]["error"].lower() or "invalid" in results[0]["error"].lower()

    def test_invalid_style(self):
        from generators.image import generate_image_data
        results = generate_image_data("test", ["image_path"], 1, [], {"style": "watercolor"})
        assert results[0]["status"] == "failed"


class TestAudioGenerator:
    def test_generate_audio_mocked(self, client, valid_audio_payload):
        mock_result = [{
            "audio_path": "/tmp/audio_0.mp3",
            "audio_base64": "base64audio",
            "transcript": "Hello, how can I help you today?",
            "language": "en",
            "voice": "nova",
            "status": "succeeded",
        }]
        with patch("generators.audio.generate_audio_data", return_value=mock_result):
            resp = client.post("/public/generate", json=valid_audio_payload)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data[0]["status"] == "succeeded"

    def test_invalid_voice(self):
        from generators.audio import generate_audio_data
        results = generate_audio_data("test", ["transcript"], 1, [], {"voice": "invalid_voice"})
        assert results[0]["status"] == "failed"
        assert "voice" in results[0]["error"].lower()


class TestVideoGenerator:
    def test_generate_video_mocked(self, client, valid_video_payload):
        mock_result = [{
            "video_path": "/tmp/video_0.mp4",
            "video_url": "https://example.com/video.mp4",
            "duration_seconds": 4.0,
            "status": "succeeded",
        }]
        with patch("generators.video.generate_video_data", return_value=mock_result):
            resp = client.post("/public/generate", json=valid_video_payload)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data[0]["status"] == "succeeded"


class TestAgentGenerator:
    def test_generate_agent_mocked(self, client, valid_agent_payload):
        mock_result = [
            {
                "task": "I need to cancel my subscription",
                "turns": [
                    {"role": "user", "content": "I need to cancel my subscription"},
                    {"role": "assistant", "content": None, "tool_calls": [{"name": "lookup_account", "args": {"email": "user@test.com"}}]},
                    {"role": "tool", "tool_name": "lookup_account", "content": '{"account_id": "123", "plan": "pro"}'},
                    {"role": "assistant", "content": "I've found your account. I can process the cancellation now."},
                ],
                "outcome": "success",
                "num_tool_calls": 1,
                "status": "succeeded",
            },
            {
                "task": "I was charged twice this month",
                "turns": [
                    {"role": "user", "content": "I was charged twice this month"},
                    {"role": "assistant", "content": None, "tool_calls": [{"name": "lookup_account", "args": {"email": "user@test.com"}}]},
                    {"role": "tool", "tool_name": "lookup_account", "content": '{"account_id": "456"}'},
                    {"role": "assistant", "content": None, "tool_calls": [{"name": "process_refund", "args": {"account_id": "456", "amount": 49}}]},
                    {"role": "tool", "tool_name": "process_refund", "content": '{"success": true, "refund_id": "REF789"}'},
                    {"role": "assistant", "content": "I've processed a refund of $49."},
                ],
                "outcome": "success",
                "num_tool_calls": 2,
                "status": "succeeded",
            },
        ]
        with patch("generators.agent.generate_agent_data", return_value=mock_result):
            resp = client.post("/public/generate", json=valid_agent_payload)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data) == 2
        assert all(row["status"] == "succeeded" for row in data)

    def test_invalid_difficulty(self):
        from generators.agent import generate_agent_data
        results = generate_agent_data("test", ["task", "turns"], 1, [], {"difficulty": "impossible"})
        assert results[0]["status"] == "failed"
        assert "difficulty" in results[0]["error"].lower()

    def test_agent_turns_structure(self):
        """Validate that mocked turns have proper structure."""
        mock_turns = [
            {"role": "user", "content": "Help me"},
            {"role": "assistant", "content": None, "tool_calls": [{"name": "lookup", "args": {}}]},
            {"role": "tool", "tool_name": "lookup", "content": "result"},
            {"role": "assistant", "content": "Done"},
        ]
        # All turns should have role
        assert all("role" in t for t in mock_turns)
        # Tool calls should reference a tool name
        tool_calls = [t for t in mock_turns if t.get("tool_calls")]
        assert all(tc["name"] for t in tool_calls for tc in t["tool_calls"])
