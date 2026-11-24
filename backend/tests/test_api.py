from conftest import auth, fixture_round, make_staff
from app.schemas import ListingInput


def test_empty_real_dataset_and_roles(client, admin, applicant, company):
    d = client.get("/api/dashboard", headers=admin).json()
    assert d["counts"]["listings"] == 0 and d["counts"]["confirmed_capacities"] == 0
    assert d["llm_mode"] == "fixture"
    assert client.get("/api/admin/evidence", headers=applicant).status_code == 403
    assert client.get("/api/agent/cases", headers=company).status_code == 403
    assert (
        client.post(
            "/api/auth/register",
            json={
                "email": "x@unit.test",
                "name": "Bad role",
                "role": "admin",
                "password": "UnitPass@12345",
            },
        ).status_code
        == 422
    )


def test_pause_review_resume_and_full_publish(client, admin, applicant, company):
    rid, lid, skill = fixture_round(
        client, admin, company, applicant, qualification=True
    )
    e = client.post(
        "/api/applicant/evidence",
        headers=applicant,
        json={
            "kind": "qualification",
            "value": "BTech",
            "excerpt": "Completed BTech degree in 2025.",
            "context": "education",
        },
    ).json()
    c = client.post(
        "/api/agent/cases", headers=applicant, json={"round_id": rid}
    ).json()
    assert c["status"] == "needs_review" and c["next_nodes"] == ["review"]
    assert any(a["tool"] == "request_human_review" for a in c["activity"])
    assert (
        client.post(
            f"/api/admin/agent/cases/{c['id']}/resume", headers=applicant
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/admin/agent/cases/{c['id']}/resume", headers=admin
        ).status_code
        == 409
    )
    assert (
        client.post(f"/api/admin/rounds/{rid}/allocate", headers=admin).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/admin/evidence/{e['id']}/review",
            headers=admin,
            json={"status": "verified"},
        ).status_code
        == 200
    )
    assert (
        client.post(f"/api/admin/agent/cases/{c['id']}/resume", headers=admin).json()[
            "status"
        ]
        == "ready"
    )
    frozen = client.post(f"/api/admin/rounds/{rid}/freeze", headers=admin)
    assert frozen.status_code == 200, frozen.text
    assert (
        client.put(
            f"/api/rounds/{rid}/choices", headers=applicant, json={"listing_ids": []}
        ).status_code
        == 409
    )
    draft = client.post(f"/api/admin/rounds/{rid}/allocate", headers=admin)
    assert draft.status_code == 200, draft.text
    d = draft.json()
    did = d["id"]
    assert d["solver_status"] == "OPTIMAL"
    assert client.get("/api/outcomes", headers=applicant).json() == []
    assert (
        client.post(f"/api/admin/drafts/{did}/publish", headers=admin).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/admin/drafts/{did}/approve",
            headers=applicant,
            json={"approved": True, "digest": d["digest"]},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/admin/drafts/{did}/approve",
            headers=admin,
            json={"approved": True, "digest": "0" * 64},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/admin/drafts/{did}/approve",
            headers=admin,
            json={"approved": True, "digest": d["digest"]},
        ).status_code
        == 200
    )
    first = client.post(f"/api/admin/drafts/{did}/publish", headers=admin).json()
    second = client.post(f"/api/admin/drafts/{did}/publish", headers=admin).json()
    assert first["published_at"] == second["published_at"]
    own = client.get("/api/outcomes", headers=applicant).json()
    assert len(own) == 1 and own[0]["outcome"] == "placed"
    company_results = client.get("/api/outcomes", headers=company).json()
    assert len(company_results) == 1
    assert "input_snapshot" not in str(own) and "groups" not in str(own)


def test_unknown_capacity_blocks_and_stale_approval(client, admin, applicant, company):
    rid, lid, skill = fixture_round(client, admin, company, applicant, capacity=False)
    client.post("/api/agent/cases", headers=applicant, json={"round_id": rid})
    assert (
        client.post(f"/api/admin/rounds/{rid}/allocate", headers=admin).status_code
        == 422
    )
    client.put(
        f"/api/rounds/{rid}/capacity",
        headers=company,
        json={
            "listing_id": lid,
            "seats": 1,
            "confirmation_reference": "UNIT confirmation",
        },
    )
    assert (
        client.post(f"/api/admin/rounds/{rid}/freeze", headers=admin).status_code == 200
    )
    d = client.post(f"/api/admin/rounds/{rid}/allocate", headers=admin).json()
    client.post(
        f"/api/admin/drafts/{d['id']}/approve",
        headers=admin,
        json={"approved": True, "digest": d["digest"]},
    )
    assert (
        client.post(
            f"/api/admin/rounds/{rid}/capacity/{lid}/revoke", headers=admin
        ).status_code
        == 200
    )
    assert (
        client.post(f"/api/admin/drafts/{d['id']}/publish", headers=admin).status_code
        == 409
    )


def test_insufficient_policy_evidence(client, admin):
    pid = client.post(
        "/api/admin/policies", headers=admin, json={"name": "No corpus fixture"}
    ).json()["id"]
    client.post(f"/api/admin/policies/{pid}/approve", headers=admin)
    response = client.post(
        "/api/policy/search",
        headers=admin,
        json={
            "policy_id": pid,
            "question": "Is there a guaranteed internship?",
            "mode": "hybrid",
        },
    ).json()
    assert response["supported"] is False and "insufficient" in response["answer"]
    assert response["citations"] == []


def test_duplicate_import_preview_and_privacy(client, admin, applicant, company):
    rid, lid, skill = fixture_round(client, admin, company, applicant)
    row = client.get("/api/listings", headers=company).json()[0]
    data = {k: v for k, v in row.items() if k in ListingInput.model_fields}
    preview = client.post(
        "/api/import/listings/preview", headers=company, json=[data]
    ).json()
    assert preview["error_count"] == 1 and "Duplicate" in str(preview)
    repeated = client.post("/api/import/listings/commit", headers=company, json=[data])
    assert repeated.status_code == 201, repeated.text
    assert repeated.json() == {"imported": 0, "ids": [lid]}
    assert client.get("/api/applicant/profile", headers=company).status_code == 403
    assert (
        client.get("/api/admin/drafts/1/export", headers=applicant).status_code == 403
    )


def test_false_qualification_cannot_be_verified(client, admin, applicant):
    e = client.post(
        "/api/applicant/evidence",
        headers=applicant,
        json={
            "kind": "qualification",
            "value": "ITI",
            "excerpt": "Collaborated with an ITI team.",
        },
    ).json()
    assert (
        client.post(
            f"/api/admin/evidence/{e['id']}/review",
            headers=admin,
            json={"status": "verified"},
        ).status_code
        == 422
    )


def test_rejected_evidence_is_not_proof_qualification_not_held(
    client, admin, applicant, company
):
    rid, lid, skill = fixture_round(
        client, admin, company, applicant, qualification=True
    )
    e = client.post(
        "/api/applicant/evidence",
        headers=applicant,
        json={
            "kind": "qualification",
            "value": "BTech",
            "excerpt": "Collaborated with a BTech team.",
        },
    ).json()
    client.post(
        f"/api/admin/evidence/{e['id']}/review",
        headers=admin,
        json={"status": "rejected"},
    )
    case = client.post(
        "/api/agent/cases", headers=applicant, json={"round_id": rid}
    ).json()
    assert case["status"] == "needs_review" and "Unverified mandatory" in str(
        case["unresolved"]
    )
    assert (
        client.post(
            f"/api/admin/evidence/{e['id']}/review",
            headers=admin,
            json={"status": "not_held"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/admin/evidence/{e['id']}/review",
            headers=admin,
            json={
                "status": "not_held",
                "note": "Unit fixture authorized reviewer confirmed qualification not held.",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/admin/agent/cases/{case['id']}/resume", headers=admin
        ).json()["status"]
        == "ready"
    )


def test_private_data_deletion_removes_derived_records(
    client, admin, applicant, company
):
    rid, lid, skill = fixture_round(client, admin, company, applicant)
    client.post(
        "/api/applicant/evidence",
        headers=applicant,
        json={
            "kind": "skill",
            "value": "Python",
            "skill_id": skill,
            "excerpt": "Built a project with Python.",
        },
    )
    client.post("/api/agent/cases", headers=applicant, json={"round_id": rid})
    response = client.delete("/api/applicant/data", headers=applicant)
    assert response.status_code == 200, response.text
    assert (
        client.get("/api/applicant/profile", headers=applicant).json()["evidence"] == []
    )
    assert client.get("/api/agent/cases", headers=applicant).json() == []


def test_authorized_import_activation_token_is_single_use(client, admin):
    payload = {
        "authorized": True,
        "profiles": [
            {
                "email": "imported@unit.test",
                "name": "Imported unit participant",
                "profile": {"consent": True},
                "evidence": [],
            }
        ],
    }
    result = client.post("/api/admin/participants/import", headers=admin, json=payload)
    assert result.status_code == 200, result.text
    token = result.json()["activation_tokens"][0]["activation_token"]
    registration = {
        "email": "imported@unit.test",
        "name": "Imported unit participant",
        "role": "applicant",
        "password": "UnitImported@12345",
        "activation_token": token,
    }
    assert client.post("/api/auth/register", json=registration).status_code == 201
    assert client.post("/api/auth/register", json=registration).status_code == 409
    assert auth(client, "imported@unit.test", "UnitImported@12345")


def test_employer_cannot_read_other_owners_listings_through_catalog_or_rounds(
    client, admin, applicant, company
):
    fixture_round(client, admin, company, applicant)
    other = make_staff(client, admin, "other@unit.test", "Different organization")
    assert client.get("/api/listings", headers=other).json() == []
    assert all(
        not s["listings"]
        for s in client.get("/api/skills", headers=other).json()["skills"]
    )
    assert all(
        not r["capacities"] for r in client.get("/api/rounds", headers=other).json()
    )


def test_extraction_evaluation_requires_authorized_deidentified_inputs(client, admin):
    assert (
        client.post(
            "/api/admin/evaluate/extraction", headers=admin, json={"records": []}
        ).status_code
        == 422
    )
    skills = client.get("/api/skills", headers=admin).json()["skills"]
    sid = next(s["id"] for s in skills if s["name"] == "Python")
    result = client.post(
        "/api/admin/evaluate/extraction",
        headers=admin,
        json={
            "authorized": True,
            "deidentified": True,
            "records": [
                {
                    "text": "Skills: Python",
                    "gold_skill_ids": [sid],
                    "gold_qualifications": [],
                }
            ],
        },
    ).json()
    assert result["results"]["alias"]["skill_precision"] == 1
    assert result["results"]["llm"]["status"] == "not_run_no_live_model"
    assert "Skills: Python" not in str(result)


def test_grounded_explanation_uses_current_applicants_verified_facts(
    client, admin, applicant, company
):
    rid, lid, skill = fixture_round(client, admin, company, applicant)
    result = client.post(f"/api/applicant/matches/{lid}/explanation", headers=applicant)
    assert result.status_code == 200, result.text
    assert "no seat has been assigned" in result.json()["text"]
    assert result.json()["mode"] == "fixture"
    assert (
        client.post(
            f"/api/applicant/matches/{lid}/explanation", headers=company
        ).status_code
        == 403
    )
