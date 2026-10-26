"""
test_seed_data.py — Verify synthetic data seeding works correctly.

Tests cover:
- Expected counts of institutions, complaints, actions.
- Idempotency: running seed() twice produces the same data.
- Test scenarios A–E can be identified via stable reference numbers.
- Data integrity: foreign keys, statuses, bureaus.
"""

import sqlite3
from pathlib import Path

import pytest

from src.database import init_db, get_connection
from src.seed_data import seed, INSTITUTIONS, COMPLAINTS, ACTION_HISTORY, SCENARIO_REFS


@pytest.fixture
def seeded_db(tmp_path):
    """Create a temporary database and seed it."""
    db = tmp_path / "test_seeded.db"
    seed(db)
    return db


# ═══════════════════════════════════════════════════════════════════════════
# Basic counts
# ═══════════════════════════════════════════════════════════════════════════

class TestSeedCounts:
    """Verify that seeding creates the expected number of records."""

    def test_institution_count(self, seeded_db):
        conn = get_connection(seeded_db)
        count = conn.execute("SELECT COUNT(*) FROM institutions;").fetchone()[0]
        conn.close()
        assert count == len(INSTITUTIONS)

    def test_complaint_count(self, seeded_db):
        conn = get_connection(seeded_db)
        count = conn.execute("SELECT COUNT(*) FROM complaints;").fetchone()[0]
        conn.close()
        assert count == len(COMPLAINTS)

    def test_complaint_count_in_range(self, seeded_db):
        """Requirement: approximately 30 to 50 complaints."""
        conn = get_connection(seeded_db)
        count = conn.execute("SELECT COUNT(*) FROM complaints;").fetchone()[0]
        conn.close()
        assert 30 <= count <= 50, f"Expected 30–50 complaints, got {count}"

    def test_institution_count_at_least_8(self, seeded_db):
        """Requirement: at least 8 fictional institutions."""
        conn = get_connection(seeded_db)
        count = conn.execute("SELECT COUNT(*) FROM institutions;").fetchone()[0]
        conn.close()
        assert count >= 8

    def test_action_history_count(self, seeded_db):
        conn = get_connection(seeded_db)
        count = conn.execute("SELECT COUNT(*) FROM action_history;").fetchone()[0]
        conn.close()
        assert count == len(ACTION_HISTORY)

    def test_multiple_bureaus(self, seeded_db):
        """Requirement: multiple bureaus including PGRC and Regulation Bureau."""
        conn = get_connection(seeded_db)
        bureaus = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT bureau FROM complaints;"
            ).fetchall()
        }
        conn.close()
        assert "PGRC" in bureaus
        assert "Regulation Bureau" in bureaus
        assert len(bureaus) >= 4, f"Expected ≥4 bureaus, got {bureaus}"


# ═══════════════════════════════════════════════════════════════════════════
# Idempotency
# ═══════════════════════════════════════════════════════════════════════════

class TestSeedIdempotency:
    """Running seed() multiple times must not duplicate records."""

    def test_institutions_stable(self, seeded_db):
        seed(seeded_db)  # second run
        conn = get_connection(seeded_db)
        count = conn.execute("SELECT COUNT(*) FROM institutions;").fetchone()[0]
        conn.close()
        assert count == len(INSTITUTIONS)

    def test_complaints_stable(self, seeded_db):
        seed(seeded_db)  # second run
        conn = get_connection(seeded_db)
        count = conn.execute("SELECT COUNT(*) FROM complaints;").fetchone()[0]
        conn.close()
        assert count == len(COMPLAINTS)

    def test_actions_stable(self, seeded_db):
        seed(seeded_db)  # second run
        conn = get_connection(seeded_db)
        count = conn.execute("SELECT COUNT(*) FROM action_history;").fetchone()[0]
        conn.close()
        assert count == len(ACTION_HISTORY)

    def test_three_runs_stable(self, tmp_path):
        """Even three runs should produce the same data."""
        db = tmp_path / "triple.db"
        seed(db)
        seed(db)
        seed(db)
        conn = get_connection(db)
        inst = conn.execute("SELECT COUNT(*) FROM institutions;").fetchone()[0]
        comp = conn.execute("SELECT COUNT(*) FROM complaints;").fetchone()[0]
        acts = conn.execute("SELECT COUNT(*) FROM action_history;").fetchone()[0]
        conn.close()
        assert inst == len(INSTITUTIONS)
        assert comp == len(COMPLAINTS)
        assert acts == len(ACTION_HISTORY)


# ═══════════════════════════════════════════════════════════════════════════
# Test scenarios A–E
# ═══════════════════════════════════════════════════════════════════════════

class TestScenarios:
    """Verify that the deliberate test scenarios exist and have expected properties."""

    def _get_complaint(self, conn, ref):
        row = conn.execute(
            "SELECT * FROM complaints WHERE reference_number = ?;", (ref,)
        ).fetchone()
        assert row is not None, f"Complaint {ref} not found"
        return dict(row)

    # ── Scenario A: same institution, same fee issue, different bureaus ──

    def test_scenario_a_exist(self, seeded_db):
        refs = SCENARIO_REFS["A_same_institution_same_issue"]
        conn = get_connection(seeded_db)
        for ref in refs:
            assert self._get_complaint(conn, ref)
        conn.close()

    def test_scenario_a_different_bureaus(self, seeded_db):
        ref1, ref2 = SCENARIO_REFS["A_same_institution_same_issue"]
        conn = get_connection(seeded_db)
        c1 = self._get_complaint(conn, ref1)
        c2 = self._get_complaint(conn, ref2)
        conn.close()
        assert c1["bureau"] != c2["bureau"], "Scenario A should have different bureaus"

    def test_scenario_a_same_category_area(self, seeded_db):
        """Both should be fee-related even if categories differ slightly."""
        ref1, ref2 = SCENARIO_REFS["A_same_institution_same_issue"]
        conn = get_connection(seeded_db)
        c1 = self._get_complaint(conn, ref1)
        c2 = self._get_complaint(conn, ref2)
        conn.close()
        assert "fee" in c1["complaint_text"].lower()
        assert "fee" in c2["complaint_text"].lower()

    # ── Scenario B: same institution, unrelated issues ──

    def test_scenario_b_same_institution(self, seeded_db):
        ref1, ref2 = SCENARIO_REFS["B_same_institution_unrelated"]
        conn = get_connection(seeded_db)
        c1 = self._get_complaint(conn, ref1)
        c2 = self._get_complaint(conn, ref2)
        conn.close()
        # Both should reference SEED-INST-001
        assert c1["institution_id"] == c2["institution_id"]

    def test_scenario_b_different_categories(self, seeded_db):
        ref1, ref2 = SCENARIO_REFS["B_same_institution_unrelated"]
        conn = get_connection(seeded_db)
        c1 = self._get_complaint(conn, ref1)
        c2 = self._get_complaint(conn, ref2)
        conn.close()
        assert c1["category"] != c2["category"]

    # ── Scenario C: similar text, different institutions ──

    def test_scenario_c_different_institutions(self, seeded_db):
        ref1, ref2 = SCENARIO_REFS["C_similar_text_different_inst"]
        conn = get_connection(seeded_db)
        c1 = self._get_complaint(conn, ref1)
        c2 = self._get_complaint(conn, ref2)
        conn.close()
        assert c1["institution_id"] != c2["institution_id"]

    def test_scenario_c_same_category(self, seeded_db):
        ref1, ref2 = SCENARIO_REFS["C_similar_text_different_inst"]
        conn = get_connection(seeded_db)
        c1 = self._get_complaint(conn, ref1)
        c2 = self._get_complaint(conn, ref2)
        conn.close()
        assert c1["category"] == c2["category"]

    # ── Scenario D: similar issue, weak evidence ──

    def test_scenario_d_different_institutions(self, seeded_db):
        ref1, ref2 = SCENARIO_REFS["D_similar_issue_weak_evidence"]
        conn = get_connection(seeded_db)
        c1 = self._get_complaint(conn, ref1)
        c2 = self._get_complaint(conn, ref2)
        conn.close()
        assert c1["institution_id"] != c2["institution_id"]

    def test_scenario_d_same_category(self, seeded_db):
        ref1, ref2 = SCENARIO_REFS["D_similar_issue_weak_evidence"]
        conn = get_connection(seeded_db)
        c1 = self._get_complaint(conn, ref1)
        c2 = self._get_complaint(conn, ref2)
        conn.close()
        assert c1["category"] == c2["category"] == "Faculty Qualification"

    # ── Scenario E: varied statuses ──

    def test_scenario_e_varied_statuses(self, seeded_db):
        refs = SCENARIO_REFS["E_varied_statuses"]
        conn = get_connection(seeded_db)
        statuses = {self._get_complaint(conn, ref)["status"] for ref in refs}
        conn.close()
        assert len(statuses) >= 2, f"Expected varied statuses, got {statuses}"
        assert "Resolved" in statuses

    def test_scenario_e_resolved_has_date_closed(self, seeded_db):
        conn = get_connection(seeded_db)
        c = self._get_complaint(conn, "SEED-C-030")
        conn.close()
        assert c["date_closed"] is not None

    def test_scenario_e_aging_case_minimal_history(self, seeded_db):
        """SEED-C-031 should have very few actions (aging case)."""
        conn = get_connection(seeded_db)
        c = self._get_complaint(conn, "SEED-C-031")
        action_count = conn.execute(
            "SELECT COUNT(*) FROM action_history WHERE complaint_id = ?;",
            (c["id"],),
        ).fetchone()[0]
        conn.close()
        assert action_count <= 2, "Aging case should have minimal actions"


# ═══════════════════════════════════════════════════════════════════════════
# Data integrity
# ═══════════════════════════════════════════════════════════════════════════

class TestDataIntegrity:
    """Verify referential integrity and data quality."""

    def test_all_complaints_have_institution(self, seeded_db):
        conn = get_connection(seeded_db)
        orphans = conn.execute(
            "SELECT COUNT(*) FROM complaints WHERE institution_id IS NULL;"
        ).fetchone()[0]
        conn.close()
        assert orphans == 0, "All seed complaints should link to an institution"

    def test_all_actions_link_to_complaint(self, seeded_db):
        conn = get_connection(seeded_db)
        orphans = conn.execute(
            """SELECT COUNT(*) FROM action_history a
               LEFT JOIN complaints c ON a.complaint_id = c.id
               WHERE c.id IS NULL;"""
        ).fetchone()[0]
        conn.close()
        assert orphans == 0

    def test_reference_numbers_unique(self, seeded_db):
        conn = get_connection(seeded_db)
        total = conn.execute("SELECT COUNT(*) FROM complaints;").fetchone()[0]
        distinct = conn.execute(
            "SELECT COUNT(DISTINCT reference_number) FROM complaints;"
        ).fetchone()[0]
        conn.close()
        assert total == distinct

    def test_valid_statuses(self, seeded_db):
        valid = {"Open", "Under Review", "Resolved", "Escalated", "Closed"}
        conn = get_connection(seeded_db)
        statuses = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT status FROM complaints;"
            ).fetchall()
        }
        conn.close()
        unexpected = statuses - valid
        assert not unexpected, f"Unexpected statuses: {unexpected}"
