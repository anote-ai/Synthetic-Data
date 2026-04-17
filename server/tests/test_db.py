"""Tests for the database layer (issue #32)."""
import json, os, sys, pytest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDbLayer:
    def setup_method(self):
        """Reset the pool singleton before each test."""
        import database.db as db_mod
        db_mod._pool = None

    def test_no_db_host_returns_none_pool(self):
        with patch.dict("os.environ", {}, clear=True):
            from database.db import _get_pool
            assert _get_pool() is None

    def test_get_connection_returns_none_when_no_host(self):
        with patch.dict("os.environ", {}, clear=True):
            import database.db as db_mod
            db_mod._pool = None
            from database.db import get_db_connection
            assert get_db_connection() is None

    def test_store_generate_request_skips_when_no_db(self):
        """No DB configured — store_generate_request must not raise."""
        with patch.dict("os.environ", {}, clear=True):
            import database.db as db_mod
            db_mod._pool = None
            from database.db import store_generate_request
            store_generate_request("user@test.com", "text", ["col"], "prompt", 5)

    def test_store_generate_request_with_mocked_db(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (42,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        import database.db as db_mod
        db_mod._pool = None

        with patch("database.db.get_db_connection", return_value=mock_conn):
            from database.db import store_generate_request
            store_generate_request("alice@test.com", "text", ["q", "a"], "test", 3)

        # Verify INSERT was called
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("INSERT INTO synthetic_requests" in c for c in calls)

    def test_user_id_for_email_existing_user(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (7,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        from database.db import user_id_for_email
        result = user_id_for_email(mock_conn, "existing@test.com")
        assert result == 7

    def test_user_id_for_email_new_user(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.lastrowid = 99
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        from database.db import user_id_for_email
        result = user_id_for_email(mock_conn, "new@test.com")
        assert result == 99

    def test_pool_init_failure_returns_none(self):
        import database.db as db_mod
        db_mod._pool = None
        with patch.dict("os.environ", {"DB_HOST": "bad-host"}):
            with patch("database.db._get_pool", return_value=None):
                from database.db import get_db_connection
                result = get_db_connection()
        assert result is None

    def test_store_request_handles_db_exception(self):
        """DB write failure must not raise — just log."""
        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = Exception("DB down")

        import database.db as db_mod
        db_mod._pool = None

        with patch("database.db.get_db_connection", return_value=mock_conn):
            from database.db import store_generate_request
            store_generate_request("user@test.com", "text", ["col"], "prompt", 1)
