"""Tests for the anote-generate SDK client."""
import pytest
import responses as responses_lib
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anote_generate import Anote, AnoteGenerate, AnoteAuthError, AnoteValidationError, AnoteServerError


@pytest.fixture
def client():
    return Anote(api_key="test-key-123", base_url="http://localhost:5000")


@responses_lib.activate
def test_generate_text_success(client):
    mock_data = [
        {"question": "What is Python?", "answer": "A language.", "status": "succeeded"},
        {"question": "What is a list?", "answer": "A collection.", "status": "succeeded"},
    ]
    responses_lib.add(
        responses_lib.POST,
        "http://localhost:5000/public/generate",
        json={"data": mock_data},
        status=200,
    )
    result = client.generate(
        task_type="text",
        columns=["question", "answer"],
        prompt="Python Q&A",
        num_rows=2,
    )
    assert len(result) == 2
    assert result[0]["question"] == "What is Python?"


@responses_lib.activate
def test_generate_raises_auth_error(client):
    responses_lib.add(
        responses_lib.POST,
        "http://localhost:5000/public/generate",
        json={"error": "Unauthorized"},
        status=401,
    )
    with pytest.raises(AnoteAuthError):
        client.generate(task_type="text", columns=["col"], prompt="test", num_rows=1)


@responses_lib.activate
def test_generate_raises_validation_error(client):
    responses_lib.add(
        responses_lib.POST,
        "http://localhost:5000/public/generate",
        json={"error": "Validation failed", "details": [{"field": "task_type", "message": "Invalid"}]},
        status=422,
    )
    with pytest.raises(AnoteValidationError) as exc_info:
        client.generate(task_type="invalid", columns=["col"], prompt="test", num_rows=1)
    assert exc_info.value.details[0]["field"] == "task_type"


def test_to_file_csv(client, tmp_path):
    data = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
    out = tmp_path / "test.csv"
    client.to_file(data, str(out))
    content = out.read_text()
    assert "name,age" in content
    assert "Alice" in content


def test_to_file_jsonl(client, tmp_path):
    data = [{"q": "Q1", "a": "A1"}, {"q": "Q2", "a": "A2"}]
    out = tmp_path / "test.jsonl"
    client.to_file(data, str(out))
    lines = out.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["q"] == "Q1"


def test_missing_api_key():
    import os
    old = os.environ.pop("ANOTE_API_KEY", None)
    old2 = os.environ.pop("OPENAI_API_KEY", None)
    try:
        with pytest.raises(ValueError, match="API key required"):
            Anote()
    finally:
        if old:
            os.environ["ANOTE_API_KEY"] = old
        if old2:
            os.environ["OPENAI_API_KEY"] = old2


def test_version_exported():
    from anote_generate import __version__
    assert __version__ == "1.0.0"


def test_anote_generate_alias_exported():
    assert AnoteGenerate is Anote
