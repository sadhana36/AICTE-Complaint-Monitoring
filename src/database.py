"""
database.py — SQLite database initialization and connection helpers.

Responsibilities:
- Create the local SQLite database file if it doesn't exist.
- Define the schema for complaints, action history, and institutions.
- Provide a reusable connection helper that the rest of the app imports.

Design notes:
- All tables use INTEGER PRIMARY KEY (SQLite's rowid alias) for simplicity.
- complaint_status defaults to 'Open' so new records are immediately visible.
- action_history is an append-only log; nothing is ever deleted from it.
- institution_name_normalized stores a lowercased / stripped version of the
  name to make fuzzy matching easier later.
"""

import sqlite3
import os
from pathlib import Path

# Default database location: data/complaints.db relative to project root.
_DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent / "data"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "complaints.db"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
-- Institutions that complaints can reference.
CREATE TABLE IF NOT EXISTS institutions (
    id                        INTEGER PRIMARY KEY,
    name                      TEXT    NOT NULL,
    name_normalized           TEXT    NOT NULL,
    identifier_code           TEXT,          -- e.g. AISHE code, DISE code
    institution_type          TEXT,          -- e.g. 'University', 'College'
    city                      TEXT,
    state                     TEXT,
    created_at                TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Core complaint records.
CREATE TABLE IF NOT EXISTS complaints (
    id                        INTEGER PRIMARY KEY,
    reference_number          TEXT    UNIQUE NOT NULL,
    institution_id            INTEGER,
    institution_name_raw      TEXT,         -- original text as entered
    complainant_name          TEXT,
    complaint_text            TEXT    NOT NULL,
    category                  TEXT,
    bureau                    TEXT,          -- handling bureau / cell
    status                    TEXT    NOT NULL DEFAULT 'Open',
    priority                  TEXT    NOT NULL DEFAULT 'Normal',
    date_received             TEXT    NOT NULL DEFAULT (date('now')),
    date_closed               TEXT,
    created_at                TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at                TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

-- Append-only action / status change log.
CREATE TABLE IF NOT EXISTS action_history (
    id                        INTEGER PRIMARY KEY,
    complaint_id              INTEGER NOT NULL,
    action_type               TEXT    NOT NULL,  -- e.g. 'Status Change', 'Note', 'Reassign'
    description               TEXT    NOT NULL,
    performed_by              TEXT,
    created_at                TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (complaint_id) REFERENCES complaints(id)
);

-- Potential relationships detected between complaints (advisory only).
CREATE TABLE IF NOT EXISTS complaint_relationships (
    id                        INTEGER PRIMARY KEY,
    complaint_id_a            INTEGER NOT NULL,
    complaint_id_b            INTEGER NOT NULL,
    relationship_type         TEXT    NOT NULL,  -- 'same_institution', 'similar_issue', 'both'
    confidence_score          REAL,
    evidence_summary          TEXT,              -- human-readable explanation
    reviewed                  INTEGER NOT NULL DEFAULT 0,  -- 0 = pending, 1 = confirmed, 2 = dismissed
    created_at                TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (complaint_id_a) REFERENCES complaints(id),
    FOREIGN KEY (complaint_id_b) REFERENCES complaints(id)
);
"""


def get_db_path() -> Path:
    """Return the resolved database file path."""
    return _DEFAULT_DB_PATH


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """
    Open (or create) an SQLite connection with sensible defaults.

    Parameters
    ----------
    db_path : Path or str, optional
        Override the default database location.  Useful for tests.

    Returns
    -------
    sqlite3.Connection
    """
    path = Path(db_path) if db_path else _DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | str | None = None) -> Path:
    """
    Ensure the database exists and all tables are created.

    Returns the path to the database file so callers can confirm location.
    """
    path = Path(db_path) if db_path else _DEFAULT_DB_PATH
    conn = get_connection(path)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
    return path


def check_health(db_path: Path | str | None = None) -> dict:
    """
    Quick health check: verify the DB is accessible and tables exist.

    Returns a dict like:
        {"status": "ok", "tables": [...], "complaint_count": N}
    or  {"status": "error", "detail": "..."}
    """
    try:
        conn = get_connection(db_path)
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            ).fetchall()
        ]
        complaint_count = conn.execute(
            "SELECT COUNT(*) FROM complaints;"
        ).fetchone()[0]
        conn.close()
        return {
            "status": "ok",
            "tables": tables,
            "complaint_count": complaint_count,
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
