"""Academic and source signals used by public internship recommendations."""

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

PUBLIC_PROVIDERS = frozenset({"lever", "greenhouse", "swayam-plus"})
VERIFICATION_MAX_AGE = timedelta(hours=8)

FIELDS = {
    "Computer Science and IT": r"computer science|cse|information technology|software|full[- ]stack|front[- ]?end|back[- ]?end|data science|machine learning|cloud support|artificial intelligence|ai engineer|python|quantum computing|edtech|game development",
    "Electronics and Communication": r"electronics|ece|embedded|vlsi|semiconductor|instrumentation|drone technology",
    "Mechanical Engineering": r"mechanical|automobile|manufacturing|tool room|mechatronics|production engineering|computer aided engineering|cae",
    "Civil Engineering": r"civil engineering|civil engineer|structural engineering|construction engineering|quantity surveying|bim modeller",
    "Electrical Engineering": r"electrical|eee|industrial automation|power systems",
    "Commerce and Finance": r"commerce|finance|financial analyst|account(?:s|ing|ancy)|b\.?\s*com|m\.?\s*com|chartered accountancy",
    "Management and Business": r"management|business administration|business development|marketing|human resources|mba|bba|hr|sales|supply chain|customer support|logistics",
    "Agriculture": r"agricultur\w*|agronomy|horticulture|agri[- ]?business",
    "Food Technology": r"food technolog\w*|food processing|food science",
    "Chemical Engineering": r"chemical engineering|chemical engineer|process engineering",
    "Design and Media": r"graphic design|ui[ /-]*ux|video edit\w*|journalism|mass communication|social media|content creat\w*",
    "Health and Social Sciences": r"psychology|psychological|mental health|social work\w*|public health|sociology",
    "Education": r"teacher education|pedagogy|educational game|instructional design",
    "Law and Public Policy": r"public policy|law student|legal intern|llb|llm degree",
}
DEGREES = {
    "bachelor's": r"bachelor'?s?|b\.?\s*tech|b\.?\s*e|b\.?\s*s|b\.?\s*sc|b\.?\s*com|bba|bca|undergraduate",
    "master's": r"master'?s?|m\.?\s*tech|m\.?\s*sc|m\.?\s*com|mba|mca|postgraduate",
    "diploma": r"diploma|polytechnic",
    "iti": r"iti|industrial training institute",
    "doctorate": r"ph\.?\s*d|doctoral|doctorate",
}
DEGREE_REQUEST = re.compile(
    r"\b(?:degrees?|bachelor'?s?|master'?s?|diploma|polytechnic|undergraduate|postgraduate|b\.?\s*tech|m\.?\s*tech|mba|bba|b\.?\s*com|m\.?\s*com|bca|mca|iti|ph\.?\s*d)\b",
    re.IGNORECASE,
)


def _terms(value, catalog):
    return {
        name
        for name, pattern in catalog.items()
        if re.search(rf"\b(?:{pattern})\b", value, re.IGNORECASE)
    }


def academic_fields(value):
    return _terms(value, FIELDS)


def education_terms(value):
    # Preserve the existing Lever education label for already imported records.
    terms = _terms(value, DEGREES)
    if re.search(
        r"\b(?:computer science|cse|software engineering)\b", value, re.IGNORECASE
    ):
        terms.add("computer science")
    return terms


def published_academics(title, requirements):
    academic_lines = "\n".join(
        line for line in requirements.splitlines() if DEGREE_REQUEST.search(line)
    )
    fields = academic_fields(title) | academic_fields(academic_lines)
    if not fields:
        fields = academic_fields(requirements)
        if re.search(r"\bPCB design\b", requirements, re.IGNORECASE):
            fields.add("Electronics and Communication")
    degrees = education_terms(academic_lines)
    for line in academic_lines.splitlines():
        if re.search(r"\bor above\b", line, re.IGNORECASE):
            levels = ("diploma", "bachelor's", "master's", "doctorate")
            minimum = next(
                (
                    idx
                    for idx, level in enumerate(levels)
                    if level in education_terms(line)
                ),
                len(levels),
            )
            degrees.update(levels[minimum:])
    return sorted(fields), sorted(degrees)


def is_managed(details):
    return details.get("source_provider") in PUBLIC_PROVIDERS


def has_public_provenance(details):
    if not (
        is_managed(details)
        and details.get("source_posting_id")
        and details.get("organization")
    ):
        return False
    try:
        return all(
            (url := urlsplit(details.get(field) or "")).scheme == "https"
            and bool(url.hostname)
            for field in ("source_url", "source_board_url", "application_url")
        )
    except ValueError:
        return False


def source_open(details, now=None):
    now = now or datetime.now(UTC)
    if not has_public_provenance(details) or details.get("source_approved") is not True:
        return False
    try:
        checked = datetime.fromisoformat(details["source_verified_at"])
        closing = details.get("source_closes_at")
        return timedelta(0) <= now - checked <= VERIFICATION_MAX_AGE and (
            not closing or now < datetime.fromisoformat(closing)
        )
    except (KeyError, TypeError, ValueError):
        return False


def profile_academics(applicant):
    text = " ".join(
        filter(
            None,
            (
                *(
                    applicant.get(key)
                    for key in (
                        "education",
                        "qualification",
                        "course",
                        "academic_branch",
                    )
                ),
                *applicant.get("qualifications", []),
            ),
        )
    )
    return academic_fields(text), education_terms(text)


def relevant_match(pair):
    components = pair["components"]
    return bool(
        pair["matched_skills"]
        or any(
            (components.get(key) or 0) > 0
            for key in ("role", "education", "sector_role")
        )
    )
