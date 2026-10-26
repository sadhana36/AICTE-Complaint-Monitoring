"""
test_database.py — Verify that the SQLite database initialises correctly.

Uses a temporary file so tests never touch the real database.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.database import init_db, get_connection, check_health


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary database path for each test."""
    return tmp_path / "test_complaints.db"


class TestInitDb:
    """Tests for init_db()."""

    def test_creates_database_file(self, tmp_db):
        result_path = init_db(tmp_db)
        assert result_path.exists(), "Database file was not created"

    def test_creates_expected_tables(self, tmp_db):
        init_db(tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        }
        conn.close()
        expected = {"institutions", "complaints", "action_history", "complaint_relationships"}
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_idempotent(self, tmp_db):
        """Calling init_db twice should not raise or lose data."""
        init_db(tmp_db)
        # Insert a row to make sure it survives a second init.
        conn = get_connection(tmp_db)
        conn.execute(
            "INSERT INTO complaints (reference_number, complaint_text) VALUES (?, ?);",
            ("REF-001", "Test complaint"),
        )
        conn.commit()
        conn.close()

        # Second init
        init_db(tmp_db)

        conn = get_connection(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM complaints;").fetchone()[0]
        conn.close()
        assert count == 1, "Data was lost after re-initialisation"


class TestCheckHealth:
    """Tests for check_health()."""

    def test_healthy_after_init(self, tmp_db):
        init_db(tmp_db)
        result = check_health(tmp_db)
        assert result["status"] == "ok"
        assert result["complaint_count"] == 0
        assert len(result["tables"]) >= 4

    def test_error_on_bad_path(self):
        # A path inside a non-existent deeply nested dir that we cannot create
        # should still return a dict (not raise).
        result = check_health("/nonexistent_root_xyz/impossible.db")
        # On Windows this may succeed (creating the path) or fail —
        # either way check_health must not crash.
        assert "status" in result


class TestGetConnection:
    """Tests for get_connection()."""

    def test_returns_connection(self, tmp_db):
        init_db(tmp_db)
        conn = get_connection(tmp_db)
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_foreign_keys_enabled(self, tmp_db):
        init_db(tmp_db)
        conn = get_connection(tmp_db)
        fk_status = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        conn.close()
        assert fk_status == 1, "Foreign keys should be enabled"
