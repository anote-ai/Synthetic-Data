"""Tests for the async language generator (issue #42)."""
import json, os, sys, pytest
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("REPLICATE_API_TOKEN", "test-token")
os.environ.setdefault("SYNTHETIC_OUTPUT_DIR", "/tmp/synthetic-test-output")


class TestLanguageGenerator:
    def _mock_client(self, content: dict):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content=json.dumps(content)))]
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=mock_resp)
        return client

    def test_default_english_generation(self):
        from generators.Language import generate_language_data
        content = {"question": "What is Python?", "answer": "A programming language."}
        with patch("generators.Language.openai.AsyncOpenAI", return_value=self._mock_client(content)):
            results = generate_language_data("Python Q&A", ["question", "answer"], 1)
        assert results[0]["status"] == "succeeded"
        assert results[0]["question"] == "What is Python?"

    def test_spanish_language_param(self):
        from generators.Language import generate_language_data
        content = {"question": "¿Qué es Python?", "answer": "Un lenguaje de programación."}
        with patch("generators.Language.openai.AsyncOpenAI", return_value=self._mock_client(content)):
            results = generate_language_data(
                "Python Q&A", ["question", "answer"], 1,
                params={"language": "Spanish"}
            )
        assert results[0]["status"] == "succeeded"

    def test_target_language_legacy_param(self):
        """target_language param (old name) still works."""
        from generators.Language import generate_language_data
        content = {"q": "What?", "a": "This."}
        with patch("generators.Language.openai.AsyncOpenAI", return_value=self._mock_client(content)):
            results = generate_language_data(
                "Q&A", ["q", "a"], 1,
                params={"target_language": "Japanese"}
            )
        assert results[0]["status"] == "succeeded"

    def test_multiple_rows(self):
        from generators.Language import generate_language_data
        content = {"question": "Q", "answer": "A"}
        with patch("generators.Language.openai.AsyncOpenAI", return_value=self._mock_client(content)):
            results = generate_language_data("test", ["question", "answer"], 3)
        assert len(results) == 3
        assert all(r["status"] == "succeeded" for r in results)

    def test_missing_api_key_returns_failed(self):
        from generators.Language import generate_language_data
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            results = generate_language_data("test", ["question"], 1)
        assert results[0]["status"] == "failed"

    def test_build_system_includes_language(self):
        from generators.Language import _lang_build_system
        system = _lang_build_system("Python Q&A", ["question", "answer"], "Japanese", [])
        assert "Japanese" in system
        assert "question" in system
        assert "answer" in system

    def test_build_system_with_examples(self):
        from generators.Language import _lang_build_system
        examples = [{"question": "What?", "answer": "This."}]
        system = _lang_build_system("test", ["question", "answer"], "English", examples)
        assert "What?" in system

    def test_via_endpoint(self, client):
        from generators.Language import generate_language_data
        mock_result = [{"question": "Q1", "answer": "A1", "status": "succeeded"}]
        with patch("generators.Language.generate_language_data", return_value=mock_result):
            resp = client.post("/public/generate", json={
                "task_type": "language",
                "prompt": "Generate Q&A pairs",
                "num_rows": 1,
                "columns": ["question", "answer"],
                "params": {"language": "French"},
            })
        assert resp.status_code == 200
        assert resp.get_json()["data"][0]["status"] == "succeeded"
