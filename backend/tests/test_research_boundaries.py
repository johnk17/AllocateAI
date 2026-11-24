from datetime import date, timedelta
from io import BytesIO

import pymupdf
from docx import Document

from conftest import auth, fixture_round


def account(client, label, password="UnitPerson2026@"):
    email = f"{label}@unit.test"
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "name": "Isolated account " + label,
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], auth(client, email, password)


def test_staff_request_has_no_privilege_and_signout_revokes_session(client, admin):
    uid, headers = account(client, "requestor")
    assert (
        client.post(
            "/api/auth/register",
            json={
                "email": "company@unit.test",
                "name": "Unauthorized company",
                "role": "company",
                "password": "UnitPerson2026@",
            },
        ).status_code
        == 422
    )
    payload = {
        "scope": "Unit-only company",
        "evidence_reference": "Unit membership evidence",
    }
    assert (
        client.post("/api/staff/request", headers=headers, json=payload).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/admin/staff/{uid}",
            headers=headers,
            json=payload | {"role": "company"},
        ).status_code
        == 403
    )
    assert (
        client.post("/api/import/listings/commit", headers=headers, json=[]).status_code
        == 403
    )
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_resume_confirmation_and_deletion_are_owner_controlled(
    client, admin, applicant
):
    _, other = account(client, "other-applicant")
    file = BytesIO()
    doc = Document()
    doc.add_paragraph("Skills: Python")
    doc.save(file)
    response = client.post(
        "/api/applicant/documents",
        headers=applicant,
        files={"file": ("unit-resume.docx", file.getvalue())},
    )
    assert response.status_code == 200, response.text
    did = response.json()["document_id"]
    evidence = client.get("/api/applicant/profile", headers=applicant).json()[
        "evidence"
    ]
    first = next(e for e in evidence if e["value"] == "Python")
    assert first["status"] in ("suggested", "needs_review")
    endpoint = f"/api/applicant/suggestions/{first['id']}"
    assert (
        client.post(endpoint, headers=other, json={"action": "accept"}).status_code
        == 404
    )
    assert (
        client.get(f"/api/applicant/documents/{did}", headers=other).status_code == 404
    )
    accepted = client.post(endpoint, headers=applicant, json={"action": "accept"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "resume_supported"
    assert accepted.json()["reviewed_by"] is None
    assert (
        client.delete(f"/api/applicant/documents/{did}", headers=other).status_code
        == 404
    )
    assert (
        client.delete(f"/api/applicant/documents/{did}", headers=applicant).status_code
        == 200
    )
    assert (
        client.get("/api/applicant/profile", headers=applicant).json()["evidence"] == []
    )


def test_verified_listing_edits_drop_approval_and_preserve_version(
    client, admin, company, applicant
):
    rid, lid, _ = fixture_round(client, admin, company, applicant)
    current = client.get("/api/listings", headers=company).json()[0]
    current = {
        k: v
        for k, v in current.items()
        if k
        in __import__(
            "app.schemas", fromlist=["ListingInput"]
        ).ListingInput.model_fields
    }
    current["title"] = "Revised isolated test role"
    resp = client.put(f"/api/listings/{lid}", headers=company, json=current)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "unverified"
    assert resp.json()["listing_version"] == 2
    assert client.get(f"/api/listings/{lid}/versions", headers=company).json()[0][
        "details"
    ]["source_approved"]
    assert (
        client.get("/api/applicant/recommendations", headers=applicant).json()[
            "recommendations"
        ]
        == []
    )
    assert (
        client.post(f"/api/admin/rounds/{rid}/freeze", headers=admin).status_code == 422
    )


def test_policy_scope_version_and_mcp_token(client, admin, applicant, monkeypatch):
    today = date.today()

    def create_document(version, effective, content, scheme="Isolated scope"):
        result = client.post(
            "/api/admin/policy-documents",
            headers=admin,
            json={
                "title": "Isolated policy test",
                "scheme": scheme,
                "scope": scheme,
                "version": version,
                "publisher": "Unit fixture publisher",
                "effective_date": effective.isoformat(),
                "source_url": "https://unit.test/policy",
                "sections": {"Article 1": content},
            },
        )
        assert result.status_code == 200, result.text
        return result.json()["id"]

    allowed = create_document(
        "v1", today, "Institutional consent is a requirement for this round."
    )
    future = create_document(
        "v2",
        today + timedelta(days=30),
        "Institutional consent is not required for this round.",
    )
    pid = client.post(
        "/api/admin/policies",
        headers=admin,
        json={
            "name": "Scoped fixture",
            "document_ids": [allowed, future],
            "config": {"scheme": "Isolated scope", "effective_date": today.isoformat()},
        },
    ).json()["id"]
    body = {
        "policy_id": pid,
        "question": "Is institutional consent a requirement?",
        "mode": "keyword",
    }
    assert (
        client.post("/api/policy/search", headers=applicant, json=body).status_code
        == 404
    )
    assert (
        client.post(f"/api/admin/policies/{pid}/approve", headers=admin).status_code
        == 200
    )
    response = client.post("/api/policy/search", headers=applicant, json=body).json()
    assert response["citations"][0]["version"] == "v1"
    assert response["citations"][0]["start"] == 0
    assert response["citations"][0]["end"] == len(response["citations"][0]["quote"])
    token = "isolated-policy-token-fixture-123456789"
    monkeypatch.setenv("MCP_POLICY_TOKEN", token)
    monkeypatch.setenv("MCP_POLICY_IDS", str(pid))
    h = {"Authorization": f"Bearer {token}"}
    assert (
        client.post("/api/mcp/policy/search", headers=applicant, json=body).status_code
        == 401
    )
    assert (
        client.post(
            "/api/mcp/policy/search", headers=h, json=body | {"policy_id": pid + 1}
        ).status_code
        == 404
    )
    assert (
        client.post("/api/mcp/policy/search", headers=h, json=body).json() == response
    )
    assert client.get("/api/applicant/profile", headers=h).status_code == 401


def test_hosted_resume_is_opt_in_and_parse_failure_is_safe(
    client, applicant, monkeypatch
):
    provider = client.app.state.provider
    monkeypatch.setattr(provider, "mode", "live")

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Private content must remain local without explicit consent"
        )

    monkeypatch.setattr(provider, "extract", forbidden)
    invalid = client.post(
        "/api/applicant/documents",
        headers=applicant,
        files={"file": ("unreadable.pdf", b"not valid")},
    )
    assert invalid.status_code == 422
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Skills: Python")
    result = client.post(
        "/api/applicant/documents",
        headers=applicant,
        files={"file": ("isolated.pdf", doc.tobytes())},
    )
    assert result.status_code == 200, result.text
    assert result.json()["mode"] == "fixture"
