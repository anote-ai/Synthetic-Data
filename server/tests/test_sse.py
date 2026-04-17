"""Tests for the SSE streaming endpoint (issue #39)."""
import json, os, sys, pytest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("REPLICATE_API_TOKEN", "test-token")
os.environ.setdefault("SYNTHETIC_OUTPUT_DIR", "/tmp/synthetic-test-output")


def _parse_sse(raw: bytes) -> list:
    """Parse SSE response into list of parsed JSON objects."""
    events = []
    for line in raw.decode().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


class TestSSEStream:
    BASE = {
        "task_type": "text",
        "prompt": "Generate Q&A pairs",
        "num_rows": 3,
        "columns": ["question", "answer"],
    }

    def test_stream_returns_event_stream_content_type(self, client):
        mock_rows = [{"question": f"Q{i}", "answer": f"A{i}", "status": "succeeded"} for i in range(3)]
        with patch("generators.text.generate_text_data", return_value=mock_rows):
            resp = client.post("/public/generate/stream", json=self.BASE)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.content_type

    def test_stream_emits_progress_events(self, client):
        mock_rows = [{"question": f"Q{i}", "answer": f"A{i}", "status": "succeeded"} for i in range(3)]
        with patch("generators.text.generate_text_data", return_value=mock_rows):
            resp = client.post("/public/generate/stream", json=self.BASE)
        events = _parse_sse(resp.data)
        progress = [e for e in events if e.get("type") == "progress"]
        assert len(progress) == 3
        assert progress[0]["row"] == 0
        assert progress[0]["data"]["question"] == "Q0"

    def test_stream_ends_with_done_event(self, client):
        mock_rows = [{"question": "Q", "answer": "A", "status": "succeeded"}] * 2
        with patch("generators.text.generate_text_data", return_value=mock_rows):
            resp = client.post("/public/generate/stream", json=self.BASE)
        events = _parse_sse(resp.data)
        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1
        assert done_events[0]["total_rows"] == 2

    def test_stream_invalid_task_type_emits_error(self, client):
        with patch("api_endpoints.handler._resolve_generator", return_value=None):
            resp = client.post("/public/generate/stream", json={**self.BASE, "task_type": "text"})
        events = _parse_sse(resp.data)
        assert any(e.get("type") == "error" for e in events)

    def test_stream_generator_exception_emits_error(self, client):
        with patch("generators.text.generate_text_data", side_effect=RuntimeError("boom")):
            resp = client.post("/public/generate/stream", json=self.BASE)
        events = _parse_sse(resp.data)
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1
        assert "boom" in error_events[0]["message"]

    def test_stream_non_json_returns_415(self, client):
        resp = client.post("/public/generate/stream", data="not json", content_type="text/plain")
        assert resp.status_code == 415

    def test_stream_401_on_bad_auth(self, client):
        from auth_utils import InvalidTokenError
        with patch("app.extractUserEmailFromRequest", side_effect=InvalidTokenError("no")):
            resp = client.post("/public/generate/stream", json=self.BASE)
        assert resp.status_code == 401

    def test_stream_row_total_in_progress_events(self, client):
        mock_rows = [{"q": f"Q{i}", "status": "succeeded"} for i in range(5)]
        with patch("generators.text.generate_text_data", return_value=mock_rows):
            resp = client.post("/public/generate/stream", json={**self.BASE, "num_rows": 5})
        events = _parse_sse(resp.data)
        progress = [e for e in events if e.get("type") == "progress"]
        assert all(e["total"] == 5 for e in progress)
