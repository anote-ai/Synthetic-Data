"""Tests for CORS, tabular generator, code generator, and quality scoring."""
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
# CORS (#31)
# ─────────────────────────────────────────────────────────────────────────────

class TestCORS:
    def test_cors_header_present_on_health(self, client):
        resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert resp.status_code == 200
        assert "Access-Control-Allow-Origin" in resp.headers

    def test_options_preflight_allowed(self, client):
        resp = client.options(
            "/public/generate",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,Authorization",
            },
        )
        assert resp.status_code in (200, 204)


# ─────────────────────────────────────────────────────────────────────────────
# Tabular generator (#46)
# ─────────────────────────────────────────────────────────────────────────────

class TestTabularGenerator:
    def test_generate_tabular_mocked_via_endpoint(self, client):
        mock_result = [
            {"user_id": "uuid-001", "name": "Alice", "age": "30", "status": "succeeded"},
            {"user_id": "uuid-002", "name": "Bob", "age": "25", "status": "succeeded"},
        ]
        with patch("generators.tabular.generate_tabular_data", return_value=mock_result):
            resp = client.post("/public/generate", json={
                "task_type": "tabular",
                "prompt": "Generate user profile data",
                "num_rows": 2,
                "columns": ["user_id", "name", "age"],
                "params": {"schema": {"age": {"type": "int", "min": 18, "max": 90}}},
            })
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data) == 2
        assert all(r["status"] == "succeeded" for r in data)

    def test_build_system_prompt_with_schema(self):
        from generators.tabular import _build_system_prompt
        schema = {"age": {"type": "int", "min": 18, "max": 90}, "email": {"type": "email"}}
        prompt = _build_system_prompt(["age", "email"], "user data", schema, [])
        assert "age" in prompt
        assert "int" in prompt
        assert "email" in prompt

    def test_build_system_prompt_with_examples(self):
        from generators.tabular import _build_system_prompt
        examples = [{"age": "25", "email": "test@example.com"}]
        prompt = _build_system_prompt(["age", "email"], "user data", {}, examples)
        assert "test@example.com" in prompt

    def test_invalid_openai_key_raises(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            from generators.tabular import _get_client
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                _get_client()

    def test_generate_tabular_with_mocked_api(self):
        from generators.tabular import generate_tabular_data

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content=json.dumps([
            {"name": "Alice", "age": "28", "email": "alice@test.com"},
            {"name": "Bob", "age": "35", "email": "bob@test.com"},
        ])))]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        with patch("generators.tabular.openai.AsyncOpenAI", return_value=mock_client):
            results = generate_tabular_data(
                "Generate user data",
                ["name", "age", "email"],
                2,
                [],
                {"schema": {"age": {"type": "int"}}},
            )

        assert len(results) == 2
        assert results[0]["status"] == "succeeded"
        assert results[0]["name"] == "Alice"


# ─────────────────────────────────────────────────────────────────────────────
# Code generator (#47)
# ─────────────────────────────────────────────────────────────────────────────

class TestCodeGenerator:
    def test_generate_code_mocked_via_endpoint(self, client):
        mock_result = [{
            "function_signature": "def add(a: int, b: int) -> int:",
            "implementation": "def add(a, b):\n    return a + b",
            "docstring": "Add two integers.",
            "status": "succeeded",
        }]
        with patch("generators.code.generate_code_data", return_value=mock_result):
            resp = client.post("/public/generate", json={
                "task_type": "code",
                "prompt": "Python utility functions",
                "num_rows": 1,
                "columns": ["function_signature", "implementation", "docstring"],
                "params": {"code_type": "function", "language": "python"},
            })
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data[0]["status"] == "succeeded"

    def test_invalid_code_type_returns_failed(self):
        from generators.code import generate_code_data
        results = generate_code_data("test", ["code"], 1, [], {"code_type": "invalid_type"})
        assert results[0]["status"] == "failed"
        assert "code_type" in results[0]["error"].lower()

    def test_invalid_language_returns_failed(self):
        from generators.code import generate_code_data
        results = generate_code_data("test", ["code"], 1, [], {"language": "brainfuck"})
        assert results[0]["status"] == "failed"
        assert "language" in results[0]["error"].lower()

    def test_python_syntax_validation_valid(self):
        from generators.code import _validate_python
        assert _validate_python("def add(a, b):\n    return a + b") is True

    def test_python_syntax_validation_invalid(self):
        from generators.code import _validate_python
        assert _validate_python("def add(a, b)\n    return a + b") is False

    def test_build_system_prompt_contains_code_type(self):
        from generators.code import _build_system_prompt
        prompt = _build_system_prompt("function", "python", ["implementation", "docstring"], "math utils")
        assert "function" in prompt
        assert "python" in prompt
        assert "math utils" in prompt

    def test_generate_code_with_mocked_api(self):
        from generators.code import generate_code_data

        code_json = json.dumps({
            "function_signature": "def multiply(a: int, b: int) -> int:",
            "implementation": "def multiply(a, b):\n    return a * b",
            "docstring": "Multiply two integers.",
        })
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content=code_json))]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        with patch("generators.code.openai.AsyncOpenAI", return_value=mock_client):
            results = generate_code_data(
                "Python math utilities",
                ["function_signature", "implementation", "docstring"],
                1,
                [],
                {"code_type": "function", "language": "python", "validate_syntax": False},
            )

        assert len(results) == 1
        assert results[0]["status"] == "succeeded"
        assert "multiply" in results[0]["function_signature"]

    def test_bugfix_code_type_via_mocked_api(self):
        from generators.code import generate_code_data

        bugfix_json = json.dumps({
            "buggy_code": "def add(a, b):\n    return a - b",
            "fixed_code": "def add(a, b):\n    return a + b",
            "bug_description": "Wrong operator used",
            "fix_explanation": "Changed - to +",
        })
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content=bugfix_json))]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        with patch("generators.code.openai.AsyncOpenAI", return_value=mock_client):
            results = generate_code_data(
                "Python bug fixes",
                ["buggy_code", "fixed_code", "bug_description"],
                1,
                [],
                {"code_type": "bugfix", "language": "python", "validate_syntax": False},
            )

        assert results[0]["status"] == "succeeded"
        assert results[0]["buggy_code"] == "def add(a, b):\n    return a - b"


# ─────────────────────────────────────────────────────────────────────────────
# Quality scoring (#44)
# ─────────────────────────────────────────────────────────────────────────────

class TestQualityUtils:
    ROWS = [
        {"name": "Alice", "score": "95"},
        {"name": "Bob", "score": "82"},
        {"name": "Alice", "score": "95"},  # duplicate of first
        {"name": "Carol", "score": ""},    # incomplete score
    ]

    def test_deduplicate_removes_exact_duplicates(self):
        from utils.quality import deduplicate
        result = deduplicate(self.ROWS)
        assert len(result) == 3
        names = [r["name"] for r in result]
        assert names.count("Alice") == 1

    def test_deduplicate_empty_list(self):
        from utils.quality import deduplicate
        assert deduplicate([]) == []

    def test_score_completeness_all_filled(self):
        from utils.quality import score_completeness
        rows = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
        scores = score_completeness(rows)
        assert scores["name"] == 1.0
        assert scores["age"] == 1.0

    def test_score_completeness_with_empty_values(self):
        from utils.quality import score_completeness
        scores = score_completeness(self.ROWS)
        assert scores["name"] == 1.0
        assert scores["score"] < 1.0

    def test_score_completeness_empty_data(self):
        from utils.quality import score_completeness
        assert score_completeness([]) == {}

    def test_score_dataset_basic(self):
        from utils.quality import score_dataset
        report = score_dataset(self.ROWS)
        assert report["total_rows"] == 4
        assert report["unique_rows"] == 3
        assert report["duplicates_removed"] == 1
        assert "completeness" in report
        assert "avg_completeness" in report
        assert "llm_review" not in report

    def test_score_dataset_with_llm_review_mocked(self):
        from utils.quality import score_dataset
        mock_review = {"score": 8, "issues": [], "suggestions": ["Add more diversity"]}
        with patch("utils.quality.llm_coherence_review", return_value=mock_review):
            report = score_dataset(self.ROWS, prompt="user data", run_llm_review=True)
        assert "llm_review" in report
        assert report["llm_review"]["score"] == 8

    def test_score_dataset_llm_review_error_handled(self):
        from utils.quality import score_dataset
        with patch("utils.quality.llm_coherence_review", side_effect=RuntimeError("API down")):
            report = score_dataset(self.ROWS, prompt="test", run_llm_review=True)
        assert "error" in report["llm_review"]


class TestQualityEndpoint:
    ROWS = [
        {"name": "Alice", "score": "95"},
        {"name": "Bob", "score": "82"},
    ]

    def test_quality_basic(self, client):
        resp = client.post("/public/generate/quality", json={"data": self.ROWS})
        assert resp.status_code == 200
        body = resp.get_json()
        assert "quality" in body
        assert body["quality"]["total_rows"] == 2

    def test_quality_with_deduplication(self, client):
        rows_with_dup = self.ROWS + [self.ROWS[0]]  # one duplicate
        resp = client.post("/public/generate/quality", json={
            "data": rows_with_dup,
            "deduplicate": True,
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert "data" in body  # deduplicated data returned
        assert len(body["data"]) == 2

    def test_quality_with_llm_review_mocked(self, client):
        mock_review = {"score": 9, "issues": [], "suggestions": []}
        with patch("utils.quality.llm_coherence_review", return_value=mock_review):
            resp = client.post("/public/generate/quality", json={
                "data": self.ROWS,
                "prompt": "user data",
                "run_llm_review": True,
            })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["quality"]["llm_review"]["score"] == 9

    def test_quality_empty_data_returns_422(self, client):
        resp = client.post("/public/generate/quality", json={"data": []})
        assert resp.status_code == 422

    def test_quality_missing_data_field_returns_422(self, client):
        resp = client.post("/public/generate/quality", json={"prompt": "test"})
        assert resp.status_code == 422

    def test_quality_non_json_returns_415(self, client):
        resp = client.post("/public/generate/quality", data="not json", content_type="text/plain")
        assert resp.status_code == 415

    def test_quality_401_on_bad_auth(self, client):
        from auth_utils import InvalidTokenError
        with patch("app.extractUserEmailFromRequest", side_effect=InvalidTokenError("no")):
            resp = client.post("/public/generate/quality", json={"data": self.ROWS})
        assert resp.status_code == 401
