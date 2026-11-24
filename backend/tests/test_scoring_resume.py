from types import SimpleNamespace
from app.skills import match_skills, claim_supported
from app.retrieval import rrf, evaluate
from app.schemas import Rules, Choices
from pydantic import ValidationError
import pytest


def skill(id, name, aliases=()):
    return SimpleNamespace(id=id, name=name, aliases=list(aliases))


def test_distinct_technologies_and_aliases():
    catalog = [
        skill(1, "Java"),
        skill(2, "JavaScript"),
        skill(3, "C"),
        skill(4, "C++"),
        skill(5, "React"),
        skill(6, "React Native"),
        skill(7, "PostgreSQL", ["Postgres"]),
        skill(8, "Kubernetes", ["k8s"]),
    ]
    matches = match_skills(
        "Skills: JavaScript, C++, React Native, Postgres, k8s", catalog
    )
    assert {s["skill_id"] for s in matches} == {2, 4, 6, 7, 8}


def test_ambiguous_terms_require_context():
    assert match_skills("Go to the R team", [skill(1, "Go"), skill(2, "R")]) == []
    assert (
        len(
            match_skills(
                "Programming languages: Go and R", [skill(1, "Go"), skill(2, "R")]
            )
        )
        == 2
    )


def test_quote_and_qualification_support():
    assert not claim_supported("qualification", "ITI", "Collaborated with an ITI team")
    assert claim_supported("qualification", "ITI", "Completed ITI certificate in 2025")
    assert not claim_supported(
        "qualification", "BTech", "Currently pursuing BTech degree"
    )
    assert not claim_supported("qualification", "BTech", "I do not hold a BTech degree")
    assert not claim_supported(
        "skill", "Python", "I have no experience in Python", skill(1, "Python")
    )


def test_rrf_and_validation():
    assert rrf([[1, 2, 3], [3, 2, 4]])[0] == 3 or rrf([[1, 2, 3], [3, 2, 4]])[0] == 2
    with pytest.raises(ValidationError):
        Rules(equity_weight=0.2)
    with pytest.raises(ValidationError):
        Choices(listing_ids=[1, 1])


def test_catalog_provenance_and_search(client, admin):
    data = client.get("/api/skills?q=Postgres", headers=admin).json()
    row = data["skills"][0]
    assert row["name"] == "PostgreSQL" and row["source_version"]
    assert "curated" in row["source"] and row["reviewed"] is False
