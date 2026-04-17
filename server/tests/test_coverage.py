"""Extended tests targeting uncovered code paths to raise overall coverage."""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENAI_API_KEY", "test-key-sk-1234")
os.environ.setdefault("REPLICATE_API_TOKEN", "test-replicate-token")
os.environ.setdefault("SYNTHETIC_OUTPUT_DIR", "/tmp/synthetic-test-output")


# ─────────────────────────────────────────────────────────────────────────────
# auth_utils.py
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthUtils:
    def _make_req(self, header_value: str):
        mock_req = MagicMock()
        mock_req.headers.get.return_value = header_value
        return mock_req

    def test_missing_header_raises(self):
        from auth_utils import extractUserEmailFromRequest, InvalidTokenError
        with pytest.raises(InvalidTokenError, match="Missing or malformed"):
            extractUserEmailFromRequest(self._make_req(""))

    def test_non_bearer_scheme_raises(self):
        from auth_utils import extractUserEmailFromRequest, InvalidTokenError
        with pytest.raises(InvalidTokenError):
            extractUserEmailFromRequest(self._make_req("Basic abc123"))

    def test_fallback_without_jwt(self):
        """When _HAS_JWT is False, any Bearer token returns the default email."""
        from auth_utils import extractUserEmailFromRequest
        with patch("auth_utils._HAS_JWT", False):
            email = extractUserEmailFromRequest(self._make_req("Bearer sometoken"))
        assert email == "user@example.com"

    def test_invalid_token_raises_when_jwt_available(self):
        from auth_utils import extractUserEmailFromRequest, InvalidTokenError, _HAS_JWT
        if not _HAS_JWT:
            pytest.skip("PyJWT not available in this environment")
        with pytest.raises(InvalidTokenError):
            extractUserEmailFromRequest(self._make_req("Bearer not.a.real.token"))

    def test_generate_token_roundtrip(self):
        from auth_utils import extractUserEmailFromRequest, generate_token, _HAS_JWT
        if not _HAS_JWT:
            pytest.skip("PyJWT not available in this environment")
        token = generate_token("alice@example.com")
        email = extractUserEmailFromRequest(self._make_req(f"Bearer {token}"))
        assert email == "alice@example.com"

    def test_generate_token_without_jwt_raises(self):
        from auth_utils import generate_token, _HAS_JWT
        if _HAS_JWT:
            pytest.skip("PyJWT is available — testing the absent-JWT path")
        with pytest.raises(RuntimeError, match="PyJWT not installed"):
            generate_token("test@example.com")

    def test_route_returns_401_on_invalid_token(self, client):
        """Patch app.extractUserEmailFromRequest to simulate an auth failure."""
        from auth_utils import InvalidTokenError
        with patch("app.extractUserEmailFromRequest", side_effect=InvalidTokenError("bad token")):
            resp = client.post(
                "/public/generate",
                json={"task_type": "text", "prompt": "test", "num_rows": 1, "columns": ["col"]},
            )
        assert resp.status_code == 401
        assert "Invalid JWT token" in resp.get_json()["error"]

    def test_missing_prompt_returns_422(self, client):
        """Empty prompt string should be caught by inline validation."""
        resp = client.post(
            "/public/generate",
            json={"task_type": "text", "prompt": "   ", "num_rows": 1, "columns": ["col"]},
        )
        assert resp.status_code == 422
        assert "prompt" in resp.get_json()["details"]


# ─────────────────────────────────────────────────────────────────────────────
# utils/export.py
# ─────────────────────────────────────────────────────────────────────────────

class TestExportUtils:
    ROWS = [
        {"name": "Alice", "score": "95", "status": "succeeded"},
        {"name": "Bob", "score": "82", "status": "succeeded"},
    ]

    def test_to_csv_basic(self):
        from utils.export import to_csv
        out = to_csv(self.ROWS)
        assert "name,score,status" in out
        assert "Alice" in out and "Bob" in out

    def test_to_csv_empty_returns_empty_string(self):
        from utils.export import to_csv
        assert to_csv([]) == ""

    def test_to_jsonl_each_line_is_valid_json(self):
        from utils.export import to_jsonl
        out = to_jsonl(self.ROWS)
        lines = out.strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            json.loads(line)

    def test_to_jsonl_preserves_values(self):
        from utils.export import to_jsonl
        out = to_jsonl(self.ROWS)
        first = json.loads(out.split("\n")[0])
        assert first["name"] == "Alice"

    def _ctx(self):
        from app import app as flask_app
        return flask_app.app_context()

    def test_make_export_response_csv(self):
        from utils.export import make_export_response
        with self._ctx():
            resp = make_export_response(self.ROWS, "csv", "out")
        assert resp.mimetype == "text/csv"
        assert b"Alice" in resp.data
        assert b"attachment" in resp.headers.get("Content-Disposition", "").encode()

    def test_make_export_response_csv_case_insensitive(self):
        from utils.export import make_export_response
        with self._ctx():
            resp = make_export_response(self.ROWS, "CSV")
        assert resp.mimetype == "text/csv"

    def test_make_export_response_jsonl(self):
        from utils.export import make_export_response
        with self._ctx():
            resp = make_export_response(self.ROWS, "jsonl")
        assert resp.mimetype == "application/jsonl"
        assert b"Alice" in resp.data

    def test_make_export_response_json(self):
        from utils.export import make_export_response
        with self._ctx():
            resp = make_export_response(self.ROWS, "json")
        assert resp.mimetype == "application/json"
        payload = json.loads(resp.data)
        assert payload["data"][0]["name"] == "Alice"

    def test_make_export_response_unknown_format_raises(self):
        from utils.export import make_export_response
        with pytest.raises(ValueError, match="Unsupported format"):
            make_export_response(self.ROWS, "xml")


# ─────────────────────────────────────────────────────────────────────────────
# app.py  —  /public/generate/export endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestExportEndpoint:
    ROWS = [{"name": "Alice", "score": "95", "status": "succeeded"}]
    BASE = {"task_type": "text", "prompt": "Generate names", "num_rows": 1, "columns": ["name"]}

    def test_export_csv(self, client):
        with patch("generators.text.generate_text_data", return_value=self.ROWS):
            resp = client.post("/public/generate/export", json={**self.BASE, "format": "csv"})
        assert resp.status_code == 200
        assert b"Alice" in resp.data

    def test_export_jsonl(self, client):
        with patch("generators.text.generate_text_data", return_value=self.ROWS):
            resp = client.post("/public/generate/export", json={**self.BASE, "format": "jsonl"})
        assert resp.status_code == 200
        assert b"Alice" in resp.data

    def test_export_json(self, client):
        with patch("generators.text.generate_text_data", return_value=self.ROWS):
            resp = client.post("/public/generate/export", json={**self.BASE, "format": "json"})
        assert resp.status_code == 200
        assert b"data" in resp.data

    def test_export_invalid_format_returns_422(self, client):
        resp = client.post("/public/generate/export", json={**self.BASE, "format": "xml"})
        assert resp.status_code == 422

    def test_export_non_json_body_returns_415(self, client):
        resp = client.post(
            "/public/generate/export", data="not json", content_type="text/plain"
        )
        assert resp.status_code == 415

    def test_export_401_on_bad_auth(self, client):
        from auth_utils import InvalidTokenError
        with patch("app.extractUserEmailFromRequest", side_effect=InvalidTokenError("no")):
            resp = client.post("/public/generate/export", json={**self.BASE, "format": "json"})
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# api_endpoints/handler.py  —  edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestHandlerEdgeCases:
    def test_task_type_in_app_but_not_registry_returns_422(self, client):
        """'tabular' passes app.py validation but is not in _GENERATOR_REGISTRY."""
        resp = client.post("/public/generate", json={
            "task_type": "tabular",
            "prompt": "Generate data",
            "num_rows": 1,
            "columns": ["col"],
        })
        assert resp.status_code == 422
        assert "error" in resp.get_json()

    def test_generator_exception_returns_failed_row(self, client):
        """If the generator function raises, handler returns a failed-status row."""
        with patch("generators.text.generate_text_data", side_effect=RuntimeError("boom")):
            resp = client.post("/public/generate", json={
                "task_type": "text",
                "prompt": "test",
                "num_rows": 1,
                "columns": ["col"],
            })
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data[0]["status"] == "failed"
        assert "boom" in data[0]["error"]

    def test_broken_generator_module_returns_422(self, client):
        """If importlib fails to load the module, _resolve_generator returns None → 422."""
        import importlib as _importlib_module

        real_import = _importlib_module.import_module

        def bad_import(name, *args, **kwargs):
            if name == "generators.text":
                raise ImportError("simulated missing dependency")
            return real_import(name, *args, **kwargs)

        with patch("api_endpoints.handler.importlib.import_module", side_effect=bad_import):
            resp = client.post("/public/generate", json={
                "task_type": "text",
                "prompt": "test",
                "num_rows": 1,
                "columns": ["col"],
            })
        assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# generators/video.py  —  unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestVideoGeneratorUnit:
    def test_missing_replicate_token_raises_on_import(self):
        import importlib
        original = sys.modules.pop("generators.video", None)
        try:
            with patch.dict("os.environ", {"REPLICATE_API_TOKEN": ""}):
                with pytest.raises(RuntimeError, match="REPLICATE_API_TOKEN"):
                    importlib.import_module("generators.video")
        finally:
            sys.modules.pop("generators.video", None)
            if original is not None:
                sys.modules["generators.video"] = original

    def test_api_non_201_returns_failed(self):
        from generators.video import generate_video_data
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Server Error"
        with patch("generators.video.requests.post", return_value=mock_resp):
            results = generate_video_data("a cat running", ["video_path"], 1, [], {})
        assert results[0]["status"] == "failed"
        assert "Failed to initiate" in results[0]["error"]

    def test_replicate_status_failed_returns_failed(self):
        from generators.video import generate_video_data
        init = MagicMock()
        init.status_code = 201
        init.json.return_value = {
            "urls": {"get": "https://api.replicate.com/v1/predictions/abc"},
            "status": "starting",
        }
        poll = MagicMock()
        poll.json.return_value = {"status": "failed"}
        with patch("generators.video.requests.post", return_value=init), \
             patch("generators.video.requests.get", return_value=poll), \
             patch("generators.video.time.sleep"):
            results = generate_video_data("a cat running", ["video_path"], 1, [], {})
        assert results[0]["status"] == "failed"

    def test_successful_video_generation(self):
        from generators.video import generate_video_data
        init = MagicMock()
        init.status_code = 201
        init.json.return_value = {
            "urls": {"get": "https://api.replicate.com/v1/predictions/abc"},
            "status": "starting",
        }
        poll = MagicMock()
        poll.json.return_value = {"status": "succeeded", "output": "https://example.com/video.mp4"}
        video_content = MagicMock()
        video_content.content = b"fake_video_bytes"
        with patch("generators.video.requests.post", return_value=init), \
             patch("generators.video.requests.get") as mock_get, \
             patch("generators.video.time.sleep"), \
             patch("builtins.open", MagicMock()):
            mock_get.return_value = poll
            results = generate_video_data("a cat running", ["video_path"], 1, [], {})
        assert results[0]["status"] == "succeeded"


# ─────────────────────────────────────────────────────────────────────────────
# generators/audio.py  —  unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAudioGeneratorUnit:
    def test_build_script_prompt_contains_scenario(self):
        from generators.audio import _build_script_prompt
        prompt = _build_script_prompt("customer support call", ["transcript"], [], 0)
        assert "customer support call" in prompt
        assert "transcript" in prompt

    def test_build_script_prompt_injects_example(self):
        from generators.audio import _build_script_prompt
        examples = [{"transcript": "Hi, how can I help you today?"}]
        prompt = _build_script_prompt("support call", ["transcript"], examples, 0)
        assert "Hi, how can I help you today?" in prompt

    def test_invalid_voice_returns_failed(self):
        from generators.audio import generate_audio_data
        results = generate_audio_data("test", ["transcript"], 1, [], {"voice": "invalid_voice"})
        assert results[0]["status"] == "failed"
        assert "voice" in results[0]["error"].lower()

    def test_invalid_tts_model_returns_failed(self):
        from generators.audio import generate_audio_data
        results = generate_audio_data("test", ["transcript"], 1, [], {"tts_model": "bad-model"})
        assert results[0]["status"] == "failed"
        assert "tts_model" in results[0]["error"].lower()

    def test_generate_audio_with_mocked_api(self):
        from generators.audio import generate_audio_data

        mock_script_resp = MagicMock()
        mock_script_resp.choices = [MagicMock(message=MagicMock(content="This is a test script."))]

        mock_tts_resp = MagicMock()
        mock_tts_resp.read.return_value = b"fake_audio_bytes"

        mock_transcription = MagicMock()
        mock_transcription.text = "This is a test script."
        mock_transcription.segments = []
        mock_transcription.language = "en"

        mock_async = MagicMock()
        mock_async.chat.completions.create = AsyncMock(return_value=mock_script_resp)
        mock_async.audio.speech.create = AsyncMock(return_value=mock_tts_resp)

        mock_sync = MagicMock()
        mock_sync.audio.transcriptions.create = MagicMock(return_value=mock_transcription)

        with patch("generators.audio.AsyncOpenAI", return_value=mock_async), \
             patch("generators.audio.OpenAI", return_value=mock_sync), \
             patch("generators.audio.OUTPUT_DIR") as mock_dir:
            mock_dir.__truediv__ = lambda self, name: MagicMock(
                write_bytes=MagicMock(),
                __str__=lambda s: f"/tmp/{name}",
            )
            mock_dir.mkdir = MagicMock()
            results = generate_audio_data("test prompt", ["transcript"], 1, [], {"voice": "nova"})

        assert len(results) == 1
        assert results[0]["status"] == "succeeded"
        assert results[0]["transcript"] == "This is a test script."


# ─────────────────────────────────────────────────────────────────────────────
# generators/agent.py  —  unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentGeneratorUnit:
    def test_format_tools_for_prompt(self):
        from generators.agent import _format_tools_for_prompt
        tools = [
            {"name": "search_kb", "description": "Search knowledge base", "parameters": {"query": "string"}},
            {"name": "send_email", "description": "Send an email", "parameters": {"to": "string"}},
        ]
        result = _format_tools_for_prompt(tools)
        assert "search_kb" in result
        assert "Search knowledge base" in result
        assert "send_email" in result

    def test_build_generation_prompt_contains_scenario(self):
        from generators.agent import _build_generation_prompt, DEFAULT_TOOLS
        result = _build_generation_prompt(
            scenario="billing support",
            tools=DEFAULT_TOOLS,
            difficulty="easy",
            outcome="success",
            columns=["task", "turns"],
            examples=[],
            index=0,
        )
        assert "billing support" in result
        assert "easy" in result.lower() or "straightforward" in result.lower()

    def test_build_generation_prompt_with_example(self):
        from generators.agent import _build_generation_prompt, DEFAULT_TOOLS
        examples = [{"task": "Cancel subscription", "turns": []}]
        result = _build_generation_prompt(
            "support", DEFAULT_TOOLS, "medium", "success", ["task"], examples, 0
        )
        assert "Cancel subscription" in result

    def test_invalid_difficulty_returns_failed(self):
        from generators.agent import generate_agent_data
        results = generate_agent_data("test", ["task", "turns"], 1, [], {"difficulty": "impossible"})
        assert results[0]["status"] == "failed"
        assert "difficulty" in results[0]["error"].lower()

    def test_generate_agent_with_mocked_api(self):
        from generators.agent import generate_agent_data

        trace_json = json.dumps({
            "task": "Cancel my subscription",
            "turns": [
                {"role": "user", "content": "Cancel my subscription"},
                {"role": "assistant", "content": "Done."},
            ],
            "outcome": "success",
            "num_tool_calls": 0,
            "resolution": "Subscription cancelled",
        })
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content=trace_json))]

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        with patch("generators.agent.AsyncOpenAI", return_value=mock_client):
            results = generate_agent_data(
                "Customer support",
                ["task", "turns", "outcome", "num_tool_calls"],
                1,
                [],
                {"difficulty": "easy"},
            )

        assert len(results) == 1
        assert results[0]["status"] == "succeeded"
        assert results[0]["task"] == "Cancel my subscription"

    def test_plan_outcomes_respects_distribution(self):
        from generators.agent import _plan_outcomes
        outcomes = _plan_outcomes(10, {"success": 0.7, "failure": 0.3})
        assert len(outcomes) == 10
        assert "success" in outcomes
        assert "failure" in outcomes
