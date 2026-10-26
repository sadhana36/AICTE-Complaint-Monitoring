"""Explainable, advisory complaint relationship detection.

This module deliberately has no database writes.  Scores are deterministic
heuristics for ranking review candidates, not calibrated probabilities and not
decisions about complaints or institutions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import re
from typing import Any, Iterable, Mapping

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# These are ranking thresholds, chosen for the synthetic demonstration data.
# They must be re-evaluated against labelled, representative records before
# being used as operational policy.
LIKELY_INSTITUTION = 0.70
LIKELY_ISSUE = 0.50
POTENTIAL_ISSUE = 0.48

_NAME_REPLACEMENTS = {
    "inst": "institute", "inst.": "institute", "tech": "technology",
    "tech.": "technology", "engg": "engineering", "engg.": "engineering",
    "univ": "university", "univ.": "university", "mgmt": "management",
    "mgmt.": "management", "dept": "department", "dept.": "department",
}
_NAME_STOPWORDS = {"of", "the", "and"}
_TOPICS = {
    "fee": ("fee", "fees", "tuition", "overcharging", "hike", "refund"),
    "placement": ("placement", "offer", "placement cell"),
    "faculty_qualification": ("qualification", "qualifications", "degree", "faculty", "lecturer"),
    "hostel_water": ("hostel", "water supply", "water"),
    "programme_approval": ("unapproved", "approval", "programme", "program"),
}


@dataclass(frozen=True)
class InstitutionMatch:
    confidence: float
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class RelationshipCandidate:
    complaint_id_a: Any
    complaint_id_b: Any
    institution_confidence: float
    issue_confidence: float
    overall_confidence: float
    classification: str
    evidence: tuple[str, ...]
    review_recommendation: str

    def to_dict(self) -> dict[str, Any]:
        """Return a serialization-friendly representation."""
        return asdict(self)


def _value(record: Mapping[str, Any], key: str) -> Any:
    return record.get(key) if record else None


def normalize_identifier(value: Any) -> str:
    """Normalize identifier formatting without attempting to infer aliases."""
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def normalize_institution_name(value: Any) -> str:
    """Normalize case, punctuation, spacing, and common institution aliases."""
    text = str(value or "").casefold().replace("&", " and ")
    tokens = re.findall(r"[a-z0-9]+", text)
    expanded = [_NAME_REPLACEMENTS.get(token, token) for token in tokens]
    return " ".join(token for token in expanded if token not in _NAME_STOPWORDS)


def _name_similarity(left: Any, right: Any) -> tuple[float, str | None]:
    left_name, right_name = normalize_institution_name(left), normalize_institution_name(right)
    if not left_name or not right_name:
        return 0.0, None
    if left_name == right_name:
        return 1.0, "normalized institution names match exactly"
    left_tokens, right_tokens = set(left_name.split()), set(right_name.split())
    token_score = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    sequence_score = SequenceMatcher(None, left_name, right_name).ratio()
    score = (token_score + sequence_score) / 2

    # "L.N." is a common short form for "Lakshmi Narasimha".  Treat a
    # matching leading initialism as supporting evidence, not an exact match.
    short, long = sorted((left_name, right_name), key=len)
    short_tokens = short.split()
    leading_letters = []
    for token in short_tokens:
        if len(token) == 1:
            leading_letters.append(token)
        else:
            break
    short_initials = "".join(leading_letters) or short.replace(" ", "")
    long_initials = "".join(token[0] for token in long.split() if token)
    if len(short_initials) >= 2 and long_initials.startswith(short_initials):
        score = max(score, 0.95)
        return score, "abbreviated institution initialism is consistent"
    return score, None


def score_institutions(
    left: Mapping[str, Any] | None,
    right: Mapping[str, Any] | None,
) -> InstitutionMatch:
    """Score two institution descriptions and provide evidence for review.

    Inputs may be database rows converted to dictionaries.  `name` (or
    `institution_name_raw`), `identifier_code`, `city`, `state`, and
    `institution_type` are recognized.  Identifier agreement is strong
    evidence but conflicts in supplied location/type reduce the score.
    """
    if not left or not right:
        return InstitutionMatch(0.0, ("institution information is missing",))

    evidence: list[str] = []
    score = 0.0
    left_identifier = normalize_identifier(_value(left, "identifier_code"))
    right_identifier = normalize_identifier(_value(right, "identifier_code"))
    if left_identifier and right_identifier:
        if left_identifier == right_identifier:
            score += 0.45
            evidence.append("normalized institution identifiers match")
        else:
            score -= 0.04
            evidence.append("institution identifiers differ")

    left_name = _value(left, "name") or _value(left, "institution_name_raw")
    right_name = _value(right, "name") or _value(right, "institution_name_raw")
    name_score, name_note = _name_similarity(left_name, right_name)
    if name_score:
        score += 0.52 * name_score
        evidence.append(f"name similarity {name_score:.2f}")
    if name_note:
        evidence.append(name_note)

    for field, label in (("city", "city"), ("state", "state"), ("institution_type", "institution type")):
        first, second = normalize_institution_name(_value(left, field)), normalize_institution_name(_value(right, field))
        if first and second:
            if first == second:
                score += 0.10 if field != "institution_type" else 0.05
                evidence.append(f"{label} agrees ({_value(left, field)})")
            else:
                score -= 0.15
                evidence.append(f"{label} conflicts ({_value(left, field)} / {_value(right, field)})")

    if not evidence:
        evidence.append("no comparable institution fields were supplied")
    return InstitutionMatch(round(max(0.0, min(1.0, score)), 3), tuple(evidence))


def _topic_hits(text: str) -> set[str]:
    lowered = text.casefold()
    return {topic for topic, terms in _TOPICS.items() if any(term in lowered for term in terms)}


def _numbers(text: str) -> set[str]:
    return {value.replace(",", "") for value in re.findall(r"\b\d[\d,]*\b", text)}


def _issue_score(left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[float, list[str]]:
    first, second = str(_value(left, "complaint_text") or "").strip(), str(_value(right, "complaint_text") or "").strip()
    evidence: list[str] = []
    if not first or not second:
        return 0.0, ["one or both complaint descriptions are missing"]
    matrix = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform([first, second])
    lexical = float(cosine_similarity(matrix[0], matrix[1])[0, 0])
    score = lexical * 0.70
    evidence.append(f"TF-IDF text similarity {lexical:.2f}")

    category_a, category_b = normalize_institution_name(_value(left, "category")), normalize_institution_name(_value(right, "category"))
    if category_a and category_b and category_a == category_b:
        score += 0.08
        evidence.append("categories agree")
    elif category_a and category_b and ("fee" in category_a and "fee" in category_b):
        score += 0.12
        evidence.append("categories are both fee-related")

    shared_topics = _topic_hits(first) & _topic_hits(second)
    if shared_topics:
        # Topic signals are deliberately bounded supporting evidence.  A fee
        # complaint has a stronger, more specific common topic than a broad
        # faculty-qualification reference, but still cannot stand alone.
        topic_weight = {
            "fee": 0.30,
            "placement": 0.20,
            "faculty_qualification": 0.10,
        }
        score += min(0.40, sum(topic_weight.get(topic, 0.10) for topic in shared_topics))
        evidence.append("shared topic terms: " + ", ".join(sorted(shared_topics)))
    shared_numbers = _numbers(first) & _numbers(second)
    if shared_numbers:
        score += 0.10
        evidence.append("shared numeric facts: " + ", ".join(sorted(shared_numbers)))
    return round(min(1.0, score), 3), evidence


def compare_complaints(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    left_institution: Mapping[str, Any] | None = None,
    right_institution: Mapping[str, Any] | None = None,
) -> RelationshipCandidate:
    """Return one advisory relationship candidate; this function never writes data."""
    left_institution = left_institution or left
    right_institution = right_institution or right
    institution = score_institutions(left_institution, right_institution)
    issue_score, issue_evidence = _issue_score(left, right)
    overall = round((institution.confidence * 0.40) + (issue_score * 0.60), 3)

    if institution.confidence >= LIKELY_INSTITUTION and issue_score >= LIKELY_ISSUE:
        classification = "likely related"
    elif issue_score >= POTENTIAL_ISSUE:
        classification = "potentially related"
    else:
        classification = "insufficient evidence"

    evidence = list(institution.evidence) + issue_evidence
    bureau_a, bureau_b = _value(left, "bureau"), _value(right, "bureau")
    if bureau_a and bureau_b and bureau_a != bureau_b:
        evidence.append(f"different bureaus ({bureau_a} / {bureau_b}); context only, not a negative signal")
    recommendation = (
        "human review required before any coordination or action"
        if classification != "insufficient evidence"
        else "no action recommended; retain only as an insufficient-evidence comparison"
    )
    return RelationshipCandidate(
        complaint_id_a=_value(left, "reference_number") or _value(left, "id"),
        complaint_id_b=_value(right, "reference_number") or _value(right, "id"),
        institution_confidence=institution.confidence,
        issue_confidence=issue_score,
        overall_confidence=overall,
        classification=classification,
        evidence=tuple(evidence),
        review_recommendation=recommendation,
    )


def detect_relationships(
    complaints: Iterable[Mapping[str, Any]],
    institutions: Mapping[Any, Mapping[str, Any]] | None = None,
) -> list[RelationshipCandidate]:
    """Compare every distinct complaint pair and return a stable ranked list."""
    records = list(complaints)
    institutions = institutions or {}
    candidates: list[RelationshipCandidate] = []
    for index, left in enumerate(records):
        for right in records[index + 1:]:
            candidates.append(compare_complaints(
                left, right,
                institutions.get(_value(left, "institution_id")),
                institutions.get(_value(right, "institution_id")),
            ))
    return sorted(candidates, key=lambda item: (-item.overall_confidence, str(item.complaint_id_a), str(item.complaint_id_b)))
