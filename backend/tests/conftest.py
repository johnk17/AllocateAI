from datetime import date
import os
import pathlib
import pytest
from fastapi.testclient import TestClient
from app.main import create_app

# Fix Windows sandbox PermissionError on pytest tmp_path: use a project-local base dir.
def pytest_configure(config):
    if config.option.basetemp:
        return
    base = pathlib.Path(__file__).resolve().parents[2] / ".pytest_tmp"
    base.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = base


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_PASSWORD", "UnitAdmin@12345")
    monkeypatch.setenv("EMBEDDING_MODE", "keyword")
    monkeypatch.setenv("LLM_MODE", "fixture")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    app = create_app("sqlite://", test=True)
    with TestClient(app) as client:
        yield client


def auth(client, email="admin@allocate.local", password="UnitAdmin@12345"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture
def admin(client):
    return auth(client)


@pytest.fixture
def applicant(client):
    client.post(
        "/api/auth/register",
        json={
            "email": "participant@unit.test",
            "name": "Unit participant",
            "role": "applicant",
            "password": "UnitPerson@12345",
        },
    )
    headers = auth(client, "participant@unit.test", "UnitPerson@12345")
    client.put(
        "/api/applicant/profile",
        headers=headers,
        json={
            "consent": True,
            "academic_score": 80,
            "preferred_locations": ["Pune"],
            "preferred_sectors": ["Technology"],
        },
    )
    return headers


def make_staff(
    client, admin, email, scope, role="company", password="UnitEmployer@12345"
):
    account = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "name": "Unit test staff account",
            "password": password,
        },
    )
    assert account.status_code == 201, account.text
    grant = client.put(
        f"/api/admin/staff/{account.json()['id']}",
        headers=admin,
        json={
            "role": role,
            "scope": scope,
            "evidence_reference": "Isolated unit fixture",
        },
    )
    assert grant.status_code == 200, grant.text
    return auth(client, email, password)


@pytest.fixture
def company(client, admin):
    return make_staff(client, admin, "employer@unit.test", "Unit fixture only")


def fixture_round(
    client, admin, company, applicant, qualification=False, capacity=True
):
    skills = client.get("/api/skills", headers=admin).json()["skills"]
    python = next(s["id"] for s in skills if s["name"] == "Python")
    listing = {
        "title": "Unit test role",
        "organization": "Unit fixture only",
        "source_name": "Unit test source",
        "source_url": "https://unit.test/role",
        "description": "Required Python. BTech degree required."
        if qualification
        else "Required Python for development projects.",
        "requirements": [
            {
                "skill_id": python,
                "classification": "required",
                "excerpt": "Required Python",
            }
        ],
        "mandatory_qualifications": ["BTech"] if qualification else [],
        "last_verified": date.today().isoformat(),
        "rolling": True,
        "status": "open",
        "work_mode": "remote",
        "sector": "Technology",
    }
    response = client.post(
        "/api/import/listings/commit", headers=company, json=[listing]
    )
    assert response.status_code == 201, response.text
    lid = response.json()["ids"][0]
    approval = client.post(
        f"/api/admin/listings/{lid}/approve",
        headers=admin,
        json={
            "expected_version": 1,
            "verification_reference": "Isolated test evidence",
        },
    )
    assert approval.status_code == 200, approval.text
    pid = client.post(
        "/api/admin/policies",
        headers=admin,
        json={
            "name": "Unit fixture neutral configuration",
            "config": {
                "coverage_confirmed": True,
                "scheme": "Unit test",
                "effective_date": date.today().isoformat(),
            },
        },
    ).json()["id"]
    client.post(f"/api/admin/policies/{pid}/approve", headers=admin)
    rid = client.post(
        "/api/admin/rounds",
        headers=admin,
        json={
            "name": "UNIT TEST ONLY",
            "policy_id": pid,
            "scope": "Unit fixture only",
            "listing_ids": [lid],
        },
    ).json()["id"]
    member = client.get("/api/auth/me", headers=applicant).json()["id"]
    authorized = client.put(
        f"/api/admin/rounds/{rid}/participation",
        headers=admin,
        json={
            "applicant_id": member,
            "evidence_reference": "Isolated participation fixture",
        },
    )
    assert authorized.status_code == 200, authorized.text
    if capacity:
        response = client.put(
            f"/api/rounds/{rid}/capacity",
            headers=company,
            json={
                "listing_id": lid,
                "seats": 1,
                "confirmation_reference": "UNIT TEST ONLY confirmation",
            },
        )
        assert response.status_code == 200, response.text
    response = client.put(
        f"/api/rounds/{rid}/choices", headers=applicant, json={"listing_ids": [lid]}
    )
    assert response.status_code == 200, response.text
    claim = client.post(
        "/api/applicant/evidence",
        headers=applicant,
        json={
            "kind": "skill",
            "value": "Python",
            "skill_id": python,
            "excerpt": "Skills: Python",
            "context": "skills_section",
        },
    )
    verified = client.post(
        f"/api/admin/evidence/{claim.json()['id']}/review",
        headers=admin,
        json={"status": "verified"},
    )
    assert verified.status_code == 200, verified.text
    return rid, lid, python
