"""Tests for dataset versioning (issue #43)."""
import json, os, sys, uuid, pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("REPLICATE_API_TOKEN", "test-token")
os.environ.setdefault("SYNTHETIC_OUTPUT_DIR", "/tmp/synthetic-test-output")

SAMPLE_ROWS = [{"q": "Q1", "a": "A1", "status": "succeeded"}]


class TestVersioningUtils:
    def test_save_version_returns_uuid(self, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version
            vid = save_version("u@t.com", "text", "prompt", ["q"], {}, SAMPLE_ROWS, 1)
        assert uuid.UUID(vid)  # valid UUID

    def test_save_version_creates_file(self, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version
            vid = save_version("u@t.com", "text", "prompt", ["q"], {}, SAMPLE_ROWS, 1)
        assert (tmp_path / f"{vid}.json").exists()

    def test_get_version_roundtrip(self, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version, get_version
            vid = save_version("u@t.com", "text", "my prompt", ["q"], {}, SAMPLE_ROWS, 1)
            record = get_version(vid)
        assert record["version_id"] == vid
        assert record["prompt"] == "my prompt"
        assert record["result_data"] == SAMPLE_ROWS

    def test_get_version_not_found_returns_none(self, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import get_version
            assert get_version("nonexistent-id") is None

    def test_list_versions_returns_user_records(self, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version, list_versions
            save_version("alice@t.com", "text", "p1", ["q"], {}, SAMPLE_ROWS, 1)
            save_version("alice@t.com", "image", "p2", ["img"], {}, SAMPLE_ROWS, 1)
            save_version("bob@t.com", "text", "p3", ["q"], {}, SAMPLE_ROWS, 1)
            versions = list_versions("alice@t.com")
        assert len(versions) == 2
        assert all(v["user_email"] == "alice@t.com" for v in versions)

    def test_list_versions_excludes_result_data(self, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version, list_versions
            save_version("u@t.com", "text", "p", ["q"], {}, SAMPLE_ROWS, 1)
            versions = list_versions("u@t.com")
        assert "result_data" not in versions[0]

    def test_save_version_tolerates_write_failure(self):
        from utils.versioning import save_version
        with patch("utils.versioning._versions_dir", side_effect=OSError("disk full")):
            vid = save_version("u@t.com", "text", "p", ["q"], {}, SAMPLE_ROWS, 1)
        assert uuid.UUID(vid)  # still returns a UUID

    def test_save_version_stores_name_and_parent(self, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version, get_version
            v1 = save_version("u@t.com", "text", "p1", ["q"], {}, SAMPLE_ROWS, 1, name="my-dataset")
            v2 = save_version("u@t.com", "text", "p2", ["q"], {}, SAMPLE_ROWS, 1, name="my-dataset", parent_version_id=v1)
            record = get_version(v2)
        assert record["name"] == "my-dataset"
        assert record["parent_version_id"] == v1

    def test_update_version_renames(self, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version, update_version, get_version
            vid = save_version("u@t.com", "text", "p", ["q"], {}, SAMPLE_ROWS, 1)
            update_version(vid, name="renamed")
            record = get_version(vid)
        assert record["name"] == "renamed"

    def test_update_version_sets_quality_score(self, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version, update_version, get_version
            vid = save_version("u@t.com", "text", "p", ["q"], {}, SAMPLE_ROWS, 1)
            update_version(vid, quality_score={"avg_completeness": 0.9})
            record = get_version(vid)
        assert record["quality_score"] == {"avg_completeness": 0.9}

    def test_update_version_unknown_id_returns_none(self, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import update_version
            assert update_version("nonexistent-id", name="x") is None

    def test_diff_versions_reports_row_and_metadata_changes(self, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version, diff_versions
            v1 = save_version("u@t.com", "text", "p1", ["q", "a"], {}, SAMPLE_ROWS, 1)
            v2_rows = [{"q": "Q2", "a": "A2", "status": "succeeded"}]
            v2 = save_version("u@t.com", "text", "p2", ["q", "a"], {}, v2_rows, 1)
            diff = diff_versions(v1, v2)
        assert diff["metadata_changes"]["prompt"] == {"from": "p1", "to": "p2"}
        assert diff["rows_added"] == v2_rows
        assert diff["rows_removed"] == SAMPLE_ROWS
        assert diff["rows_unchanged"] == 0

    def test_diff_versions_unknown_id_returns_none(self, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version, diff_versions
            v1 = save_version("u@t.com", "text", "p1", ["q"], {}, SAMPLE_ROWS, 1)
            assert diff_versions(v1, "nonexistent-id") is None


class TestVersioningEndpoints:
    def test_generate_returns_version_id(self, client):
        mock_rows = [{"q": "Q1", "a": "A1", "status": "succeeded"}]
        with patch("generators.text.generate_text_data", return_value=mock_rows), \
             patch("utils.versioning.save_version", return_value="test-uuid-1234"):
            resp = client.post("/public/generate", json={
                "task_type": "text", "prompt": "test", "num_rows": 1, "columns": ["q", "a"],
            })
        assert resp.status_code == 200
        body = resp.get_json()
        assert "version_id" in body
        assert body["version_id"] == "test-uuid-1234"

    def test_list_versions_endpoint(self, client, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version
            with patch("app.extractUserEmailFromRequest", return_value="test@example.com"):
                save_version("test@example.com", "text", "p", ["q"], {}, SAMPLE_ROWS, 1)
            resp = client.get("/public/generate/versions")
        assert resp.status_code == 200
        assert "versions" in resp.get_json()

    def test_get_version_endpoint(self, client, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version
            vid = save_version("test@example.com", "text", "prompt", ["q"], {}, SAMPLE_ROWS, 1)
            resp = client.get(f"/public/generate/versions/{vid}")
        assert resp.status_code == 200
        assert resp.get_json()["version_id"] == vid

    def test_get_version_not_found_returns_404(self, client, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            resp = client.get("/public/generate/versions/does-not-exist")
        assert resp.status_code == 404

    def test_list_versions_401_on_bad_auth(self, client):
        from auth_utils import InvalidTokenError
        with patch("app.extractUserEmailFromRequest", side_effect=InvalidTokenError("no")):
            resp = client.get("/public/generate/versions")
        assert resp.status_code == 401

    def test_get_version_401_on_bad_auth(self, client):
        from auth_utils import InvalidTokenError
        with patch("app.extractUserEmailFromRequest", side_effect=InvalidTokenError("no")):
            resp = client.get("/public/generate/versions/some-id")
        assert resp.status_code == 401

    def test_generate_stream_saves_version(self, client, tmp_path):
        mock_rows = [{"q": "Q1", "a": "A1", "status": "succeeded"}]
        with patch("utils.versioning._VERSIONS_DIR", tmp_path), \
             patch("generators.text.generate_text_data", return_value=mock_rows):
            resp = client.post("/public/generate/stream", json={
                "task_type": "text", "prompt": "test", "num_rows": 1, "columns": ["q", "a"],
            })
            body = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert '"type": "done"' in body
        # A version_id was minted and persisted to the file store
        version_files = list(tmp_path.glob("*.json"))
        assert len(version_files) == 1

    def test_generate_stream_links_parent_version(self, client, tmp_path):
        mock_rows = [{"q": "Q1", "a": "A1", "status": "succeeded"}]
        with patch("utils.versioning._VERSIONS_DIR", tmp_path), \
             patch("generators.text.generate_text_data", return_value=mock_rows):
            resp = client.post("/public/generate/stream", json={
                "task_type": "text", "prompt": "test", "num_rows": 1, "columns": ["q", "a"],
                "dataset_name": "chain", "parent_version_id": "parent-uuid",
            })
            resp.get_data()  # force the SSE generator to run to completion
            record = json.loads(next(tmp_path.glob("*.json")).read_text())
        assert record["name"] == "chain"
        assert record["parent_version_id"] == "parent-uuid"


class TestVersioningMutationEndpoints:
    def test_rename_version_endpoint(self, client, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version
            vid = save_version("test@example.com", "text", "p", ["q"], {}, SAMPLE_ROWS, 1)
            resp = client.patch(f"/public/generate/versions/{vid}", json={"name": "renamed"})
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "renamed"

    def test_rename_version_not_found(self, client, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            resp = client.patch("/public/generate/versions/does-not-exist", json={"name": "x"})
        assert resp.status_code == 404

    def test_rename_version_requires_body(self, client, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version
            vid = save_version("test@example.com", "text", "p", ["q"], {}, SAMPLE_ROWS, 1)
            resp = client.patch(f"/public/generate/versions/{vid}", json={})
        assert resp.status_code == 422

    def test_diff_endpoint(self, client, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version
            v1 = save_version("test@example.com", "text", "p1", ["q"], {}, SAMPLE_ROWS, 1)
            v2 = save_version("test@example.com", "text", "p2", ["q"], {}, SAMPLE_ROWS, 1)
            resp = client.get(f"/public/generate/versions/{v1}/diff?against={v2}")
        assert resp.status_code == 200
        assert resp.get_json()["metadata_changes"]["prompt"] == {"from": "p1", "to": "p2"}

    def test_diff_endpoint_requires_against_param(self, client, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version
            v1 = save_version("test@example.com", "text", "p1", ["q"], {}, SAMPLE_ROWS, 1)
            resp = client.get(f"/public/generate/versions/{v1}/diff")
        assert resp.status_code == 422

    def test_diff_endpoint_not_found(self, client, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version
            v1 = save_version("test@example.com", "text", "p1", ["q"], {}, SAMPLE_ROWS, 1)
            resp = client.get(f"/public/generate/versions/{v1}/diff?against=does-not-exist")
        assert resp.status_code == 404

    def test_restore_endpoint_creates_new_version_with_lineage(self, client, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            from utils.versioning import save_version
            vid = save_version("test@example.com", "text", "p", ["q"], {}, SAMPLE_ROWS, 1, name="ds")
            resp = client.post(f"/public/generate/versions/{vid}/restore")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["version_id"] != vid
        assert body["parent_version_id"] == vid
        assert body["name"] == "ds"
        assert body["result_data"] == SAMPLE_ROWS

    def test_restore_endpoint_not_found(self, client, tmp_path):
        with patch("utils.versioning._VERSIONS_DIR", tmp_path):
            resp = client.post("/public/generate/versions/does-not-exist/restore")
        assert resp.status_code == 404
