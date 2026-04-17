"""Tests for async job queue (issue #40)."""
import json
import time
import pytest
from unittest.mock import MagicMock, patch


# ── utils/jobs.py unit tests ──────────────────────────────────────────────────

class TestJobStore:
    def test_create_and_read_job(self, tmp_path):
        with patch("utils.jobs._JOBS_DIR", tmp_path):
            from utils.jobs import create_job, get_job
            job = create_job("text", "user@test.com", {"num_rows": 5})
            assert job["status"] == "queued"
            assert job["progress"]["total"] == 5

            fetched = get_job(job["job_id"])
            assert fetched["job_id"] == job["job_id"]
            assert fetched["task_type"] == "text"

    def test_update_job(self, tmp_path):
        with patch("utils.jobs._JOBS_DIR", tmp_path):
            from utils.jobs import create_job, update_job, get_job
            job = create_job("text", "u@test.com", {"num_rows": 3})
            update_job(job["job_id"], status="running")
            assert get_job(job["job_id"])["status"] == "running"

    def test_cancel_queued_job(self, tmp_path):
        with patch("utils.jobs._JOBS_DIR", tmp_path):
            from utils.jobs import create_job, cancel_job
            job = create_job("text", "u@test.com", {})
            canceled = cancel_job(job["job_id"])
            assert canceled["status"] == "canceled"

    def test_cancel_succeeded_job_unchanged(self, tmp_path):
        with patch("utils.jobs._JOBS_DIR", tmp_path):
            from utils.jobs import create_job, update_job, cancel_job
            job = create_job("text", "u@test.com", {})
            update_job(job["job_id"], status="succeeded")
            result = cancel_job(job["job_id"])
            assert result["status"] == "succeeded"  # not changed

    def test_get_nonexistent_job_returns_none(self, tmp_path):
        with patch("utils.jobs._JOBS_DIR", tmp_path):
            from utils.jobs import get_job
            assert get_job("nonexistent-id") is None

    def test_cancel_nonexistent_returns_none(self, tmp_path):
        with patch("utils.jobs._JOBS_DIR", tmp_path):
            from utils.jobs import cancel_job
            assert cancel_job("no-such-id") is None

    def test_job_webhook_url_stored(self, tmp_path):
        with patch("utils.jobs._JOBS_DIR", tmp_path):
            from utils.jobs import create_job
            job = create_job("text", "u@test.com", {"webhook_url": "https://example.com/hook"})
            assert job["webhook_url"] == "https://example.com/hook"


class TestWebhookDelivery:
    def test_no_webhook_url_skips(self, tmp_path):
        with patch("utils.jobs._JOBS_DIR", tmp_path):
            from utils.jobs import _send_webhook
            job = {"job_id": "abc", "status": "succeeded", "result": [], "webhook_url": None}
            _send_webhook(job)  # should not raise

    def test_webhook_sent_with_signature(self, tmp_path):
        with patch("utils.jobs._JOBS_DIR", tmp_path), \
             patch.dict("os.environ", {"WEBHOOK_SECRET": "mysecret"}):
            import httpx
            from utils.jobs import _send_webhook
            mock_post = MagicMock()
            with patch("httpx.post", mock_post):
                job = {
                    "job_id": "abc", "status": "succeeded",
                    "result": [{"col": "val"}], "webhook_url": "https://hook.example.com/cb",
                }
                _send_webhook(job)
            mock_post.assert_called_once()
            _, kwargs = mock_post.call_args
            assert "X-Signature-SHA256" in kwargs["headers"]
            assert kwargs["headers"]["X-Signature-SHA256"].startswith("sha256=")

    def test_webhook_failure_does_not_raise(self, tmp_path):
        with patch("utils.jobs._JOBS_DIR", tmp_path):
            from utils.jobs import _send_webhook
            import httpx
            with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
                job = {"job_id": "x", "status": "succeeded", "result": [], "webhook_url": "http://bad"}
                _send_webhook(job)  # should not raise


class TestJobThreadWorker:
    def test_successful_threaded_job(self, tmp_path):
        with patch("utils.jobs._JOBS_DIR", tmp_path):
            from utils.jobs import create_job, get_job, _run_job_in_thread
            job = create_job("text", "u@test.com", {"num_rows": 2})
            mock_rows = [{"q": "Q1", "status": "succeeded"}, {"q": "Q2", "status": "succeeded"}]
            with patch("api_endpoints.handler._resolve_generator", return_value=lambda *a, **k: mock_rows):
                _run_job_in_thread(
                    job["job_id"],
                    {"task_type": "text", "prompt": "test", "columns": ["q"], "num_rows": 2, "examples": [], "params": {}},
                    "u@test.com",
                )
            done = get_job(job["job_id"])
            assert done["status"] == "succeeded"
            assert done["result"] == mock_rows

    def test_failed_threaded_job(self, tmp_path):
        with patch("utils.jobs._JOBS_DIR", tmp_path):
            from utils.jobs import create_job, get_job, _run_job_in_thread
            job = create_job("text", "u@test.com", {})
            with patch("api_endpoints.handler._resolve_generator", side_effect=ValueError("boom")):
                _run_job_in_thread(
                    job["job_id"],
                    {"task_type": "text", "prompt": "x", "columns": ["c"], "num_rows": 1, "examples": [], "params": {}},
                    "u@test.com",
                )
            done = get_job(job["job_id"])
            assert done["status"] == "failed"
            assert "boom" in done["error"]

    def test_unsupported_task_type_fails(self, tmp_path):
        with patch("utils.jobs._JOBS_DIR", tmp_path):
            from utils.jobs import create_job, get_job, _run_job_in_thread
            job = create_job("unknown", "u@test.com", {})
            with patch("api_endpoints.handler._resolve_generator", return_value=None):
                _run_job_in_thread(
                    job["job_id"],
                    {"task_type": "unknown", "prompt": "x", "columns": ["c"], "num_rows": 1, "examples": [], "params": {}},
                    "u@test.com",
                )
            done = get_job(job["job_id"])
            assert done["status"] == "failed"


# ── HTTP endpoint tests ───────────────────────────────────────────────────────

class TestAsyncEndpoints:
    @pytest.fixture
    def client(self, tmp_path):
        import sys, importlib
        sys.modules.pop("utils.jobs", None)
        with patch("utils.jobs._JOBS_DIR", tmp_path):
            import app as app_module
            app_module.app.config["TESTING"] = True
            with app_module.app.test_client() as c:
                yield c

    def _auth_headers(self):
        return {"Authorization": "Bearer test-key"}

    def test_submit_job_returns_202(self, client, tmp_path):
        payload = {"task_type": "text", "prompt": "test", "columns": ["q"], "num_rows": 2}
        mock_job = {"job_id": "abc123", "status": "queued"}
        with patch("utils.jobs.submit_job", return_value=mock_job):
            resp = client.post("/public/generate/async", json=payload, headers=self._auth_headers())
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["job_id"] == "abc123"
        assert data["status"] == "queued"

    def test_submit_job_missing_task_type(self, client, tmp_path):
        payload = {"prompt": "test", "columns": ["q"]}
        resp = client.post("/public/generate/async", json=payload, headers=self._auth_headers())
        assert resp.status_code == 422

    def test_get_job_found(self, client, tmp_path):
        mock_job = {"job_id": "abc", "status": "succeeded", "result": []}
        with patch("utils.jobs.get_job", return_value=mock_job):
            resp = client.get("/public/jobs/abc", headers=self._auth_headers())
        assert resp.status_code == 200
        assert resp.get_json()["job_id"] == "abc"

    def test_get_job_not_found(self, client):
        with patch("utils.jobs.get_job", return_value=None):
            resp = client.get("/public/jobs/missing", headers=self._auth_headers())
        assert resp.status_code == 404

    def test_cancel_job(self, client):
        mock_job = {"job_id": "abc", "status": "canceled"}
        with patch("utils.jobs.cancel_job", return_value=mock_job):
            resp = client.delete("/public/jobs/abc", headers=self._auth_headers())
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "canceled"

    def test_cancel_job_not_found(self, client):
        with patch("utils.jobs.cancel_job", return_value=None):
            resp = client.delete("/public/jobs/missing", headers=self._auth_headers())
        assert resp.status_code == 404
