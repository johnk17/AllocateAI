from copy import deepcopy
from datetime import date

APPROVED = {"coverage_confirmed": True, "scheme": "Unit test", "policy_version": 1}
from app.engine import (
    optimize,
    pairs_for,
    eligible,
    score,
    verify_draft,
    listing_status,
)


def person(id=1, **kwargs):
    return dict(
        id=id,
        skills=[1],
        reviewed_skills=[1],
        qualifications=["BTech"],
        rejected_qualifications=[],
        pending_skills=[],
        groups=[],
        academic_score=80,
        preferred_locations=["Pune"],
        preferred_sectors=["Technology"],
        willing_to_relocate=True,
        prior_participation=False,
        rankings=[1],
        **kwargs,
    )


def listing(id=1, capacity=1):
    return {
        "id": id,
        "capacity": capacity,
        "status": "open",
        "last_verified": date.today().isoformat(),
        "source_approved": True,
        "rolling": True,
        "deadline": None,
        "mandatory_qualifications": ["BTech"],
        "requirements": [{"skill_id": 1, "classification": "required"}],
        "sector": "Technology",
        "location": "Pune",
    }


def test_capacity_single_assignment_and_ranked_only():
    a = [person(1), person(2), person(3)]
    i = [listing()]
    r = optimize(a, i, APPROVED)
    assert len(r["placements"]) == 1 and r["solver_status"] == "OPTIMAL"
    assert not verify_draft(r)
    assert len(set(p["applicant_id"] for p in r["placements"])) == 1
    assert all(p["listing_id"] == 1 for p in r["placements"])


def test_unknown_capacity_never_assigns():
    r = optimize([person()], [listing(capacity=None)], APPROVED)
    assert r["placements"] == [] and r["excluded"][0]["status"] == "recommendation_only"


def test_unverified_qualification_blocks_instead_of_fail():
    a = person()
    a["qualifications"] = []
    assert eligible(a, listing(), APPROVED)["status"] == "needs_review"
    assert optimize([a], [listing()], APPROVED)["placements"] == []
    a["rejected_qualifications"] = ["BTech"]
    assert eligible(a, listing(), APPROVED)["status"] == "ineligible"


def test_pending_required_skill_blocks():
    a = person()
    a["skills"] = []
    a["pending_skills"] = [1]
    a["reviewed_skills"] = []
    assert optimize([a], [listing()], APPROVED)["placements"] == []


def test_preference_not_restriction_and_expiry():
    a = person()
    i = listing()
    i["location"] = "Delhi"
    assert eligible(a, i, APPROVED)["status"] == "eligible"
    a["willing_to_relocate"] = False
    a["home_location"] = "Pune"
    assert eligible(a, i, APPROVED)["status"] == "ineligible"
    i["deadline"] = "2020-01-01"
    assert listing_status(i) == "expired"


def test_unavailable_components_renormalized():
    a = person()
    a["academic_score"] = None
    i = listing()
    i["sector"] = None
    s = score(a, i, APPROVED)
    assert s["evidence_coverage"] == 0.7 and s["score"] == 100
    assert s["contributions"]["work_mode"] is None
    b = deepcopy(a)
    b["groups"] = ["SC", "women"]
    assert score(a, i, APPROVED)["merit_score"] == score(b, i, APPROVED)["merit_score"]


def test_independent_verifier_catches_tampering():
    r = optimize([person(1), person(2)], [listing()], APPROVED)
    r["placements"] *= 2
    assert any("duplicate" in e or "capacity" in e for e in verify_draft(r))


def test_infeasible_groups_not_relaxed():
    r = optimize([person()], [listing()], APPROVED | {"minimum_placements": {"PwD": 3}})
    assert (
        r["solver_status"] == "INFEASIBLE" and not r["publishable"] and r["conflicts"]
    )


def test_placement_count_before_quality():
    a, b = person(1), person(2)
    a["rankings"] = [1, 2]
    b["rankings"] = [1]
    r = optimize([a, b], [listing(1), listing(2)], APPROVED)
    assert len(r["placements"]) == 2


def test_rank_tie_breaking():
    a, b = person(1), person(2)
    a["rankings"] = [1, 2]
    b["rankings"] = [2, 1]
    r = optimize([a, b], [listing(1), listing(2)], APPROVED)
    assert all(p["rank"] == 1 for p in r["placements"])


def test_policy_requires_approved_coverage_and_noc():
    assert eligible(person(), listing(), {})["decision"] == "REVIEW"
    rules = APPROVED | {"require_noc": True}
    assert eligible(person(), listing(), rules)["decision"] == "REVIEW"
    p = person()
    p["noc_confirmed"] = True
    assert eligible(p, listing(), rules)["decision"] == "PASS"


def test_missing_evidence_and_weighted_skill_overlap():
    assert score({}, {}, APPROVED)["score"] is None
    s = score(
        {"skills": [2]},
        {
            "requirements": [
                {"skill_id": 1, "classification": "required"},
                {"skill_id": 2, "classification": "preferred"},
                {"skill_id": 3, "classification": "mentioned"},
            ],
            "unresolved_requirements": ["Trade term requires mapping"],
        },
        APPROVED,
    )
    assert s["skill_coverage"] == 1 / 3
    assert s["skill_coverage_status"] == "partial"
    assert s["missing_skills"] == [1]
