"""Focused tests for read-only, explainable relationship detection."""

from src.relationship_detection import (
    compare_complaints,
    detect_relationships,
    normalize_institution_name,
    score_institutions,
)
from src.seed_data import COMPLAINTS, INSTITUTIONS


def _complaint(reference):
    return next(item for item in COMPLAINTS if item["reference_number"] == reference)


def _institution(code):
    values = next(item for item in INSTITUTIONS if item[0] == code)
    return {
        "identifier_code": values[0], "name": values[1],
        "institution_type": values[3], "city": values[4], "state": values[5],
    }


def _compare(first, second):
    left, right = _complaint(first), _complaint(second)
    return compare_complaints(
        left, right, _institution(left["institution_code"]), _institution(right["institution_code"])
    )


def test_scenario_a_is_likely_related_across_bureaus():
    result = _compare("SEED-C-001", "SEED-C-002")
    assert result.classification == "likely related"
    assert result.institution_confidence >= 0.70
    assert result.issue_confidence >= 0.50
    assert any("different bureaus" in line for line in result.evidence)
    assert "human review required" in result.review_recommendation


def test_scenario_b_same_institution_is_not_same_issue_by_itself():
    result = _compare("SEED-C-001", "SEED-C-003")
    assert result.institution_confidence >= 0.70
    assert result.issue_confidence < 0.48
    assert result.classification == "insufficient evidence"


def test_scenario_c_is_potential_issue_relationship_not_same_institution():
    result = _compare("SEED-C-010", "SEED-C-011")
    assert result.institution_confidence < 0.70
    assert result.issue_confidence >= 0.48
    assert result.classification == "potentially related"


def test_scenario_d_remains_ambiguous():
    result = _compare("SEED-C-020", "SEED-C-021")
    assert result.classification == "insufficient evidence"
    assert result.institution_confidence < 0.70


def test_name_normalization_and_abbreviation_evidence():
    assert normalize_institution_name(" L.N. Institute of Tech. ") == "l n institute technology"
    result = score_institutions(
        {"name": "Lakshmi Narasimha Institute of Technology", "city": "Vijayawada"},
        {"name": "L.N. Institute of Tech.", "city": "Vijayawada"},
    )
    assert result.confidence >= 0.38
    assert any("initialism" in line for line in result.evidence)


def test_matching_identifier_is_reduced_by_conflicting_location():
    result = score_institutions(
        {"identifier_code": "AISHE-123", "name": "North College", "city": "Pune", "state": "Maharashtra"},
        {"identifier_code": "aishe 123", "name": "Different Institute", "city": "Kolkata", "state": "West Bengal"},
    )
    assert result.confidence < 0.70
    assert any("identifiers match" in line for line in result.evidence)
    assert any("conflicts" in line for line in result.evidence)


def test_missing_identifiers_and_missing_text_are_explained():
    result = compare_complaints(
        {"reference_number": "A", "institution_name_raw": "Example College", "complaint_text": ""},
        {"reference_number": "B", "institution_name_raw": "Example College", "complaint_text": None},
    )
    assert result.issue_confidence == 0
    assert result.classification == "insufficient evidence"
    assert any("descriptions are missing" in line for line in result.evidence)


def test_empty_input_and_output_are_deterministic():
    assert detect_relationships([]) == []
    complaints = [_complaint("SEED-C-001"), _complaint("SEED-C-002"), _complaint("SEED-C-003")]
    first = detect_relationships(complaints)
    second = detect_relationships(complaints)
    assert first == second
    assert first[0].complaint_id_a == "SEED-C-001"
    assert first[0].complaint_id_b == "SEED-C-002"


def test_evidence_and_serializable_scores_are_present():
    result = _compare("SEED-C-001", "SEED-C-002")
    payload = result.to_dict()
    assert payload["institution_confidence"] >= 0
    assert payload["issue_confidence"] >= 0
    assert payload["evidence"]
