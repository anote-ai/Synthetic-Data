import pytest
from flask import Flask
from app import app as flask_app

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client

def test_generate_text(client):
    payload = {
        "task_type": "text",
        "prompt": "Generate test Q&A",
        "num_rows": 2,
        "columns": ["question", "answer"],
        "examples": [{"question": "What is 2+2?", "answer": "4"}]
    }
    headers = {"Authorization": "Bearer test-api-key"}
    response = client.post("/public/generate", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert "data" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 2
    assert all("question" in row and "answer" in row for row in data["data"])
