import json
from datetime import timedelta

import httpx
import pytest
from app.db import Listing, User, utcnow
from app.engine import listing_status
from app.main import create_app
from app.public_feed import SWAYAM, BoardResult, _swayam_posting
from fastapi.testclient import TestClient

KEY = "10000000-0000-4000-8000-000000000001"
URL = f"{SWAYAM}/internships/{KEY}"


def test_portal_requires_live_apply_control_and_unexpired_deadline():
    now = utcnow()
    job = {
        "@type": "JobPosting",
        "title": "Civil Engineering Intern",
        "description": "Assist the team with construction drawings.",
        "employmentType": "INTERN",
        "hiringOrganization": {"name": "Test-only employer"},
        "jobLocation": {"address": {"addressCountry": "IN", "addressLocality": "Pune"}},
        "validThrough": (now + timedelta(hours=1)).isoformat(),
    }
    result = BoardResult("swayam-plus", "swayam-plus", f"{SWAYAM}/internships")

    def posting(button):
        html = f'<script type="application/ld+json">{json.dumps(job)}</script>{button}'
        return httpx.MockTransport(
            lambda req: httpx.Response(
                200, headers={"Content-Type": "text/html"}, text=html
            )
        )

    with httpx.Client(
        transport=posting('<button class="disabled:opacity-60">Apply Now</button>')
    ) as client:
        details = _swayam_posting(client, result, KEY)
        assert listing_status(details) == "open"
        assert details["application_url"] == URL
        assert (
            listing_status(
                details
                | {"source_closes_at": (now - timedelta(seconds=10)).isoformat()}
            )
            != "open"
        )
        assert (
            listing_status(
                details | {"source_verified_at": (now - timedelta(hours=9)).isoformat()}
            )
            != "open"
        )
    with (
        httpx.Client(transport=posting('<button disabled="">Apply Now</button>')) as client,
        pytest.raises(ValueError, match="Apply control unavailable"),
    ):
        _swayam_posting(client, result, KEY)


def test_applicant_recommendations_require_live_provenance_and_profile_match(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("ADMIN_PASSWORD", "IsolatedTestAdmin@123")
    monkeypatch.setenv("ALLOCATEAI_LOCAL_SQLITE", "1")
    monkeypatch.delenv("ALLOCATEAI_E2E_FIXTURES", raising=False)
    monkeypatch.setenv("EMBEDDING_MODE", "keyword")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    app = create_app(f"sqlite:///{tmp_path / 'isolated.db'}")
    now = utcnow()
    original = {
        "organization": "Isolated test employer",
        "description": "Test-only record",
        "source_name": "Test-only posting",
        "title": "Civil Engineering Intern",
        "source_board_url": f"{SWAYAM}/internships",
        "source_provider": "swayam-plus",
        "source_posting_id": KEY,
        "source_url": URL,
        "application_url": URL,
        "academic_fields": ["Civil Engineering"],
        "status": "open",
        "source_approved": True,
        "source_verified_at": now.isoformat(),
        "source_closes_at": (now + timedelta(days=1)).isoformat(),
    }
    with TestClient(app) as client:
        with app.state.Session() as db:
            owner = db.query(User).filter_by(role="admin").first()
            db.add(Listing(owner_id=owner.id, source_url=URL, details=original))
            stale = original | {
                "source_url": URL + "?stale",
                "source_verified_at": (now - timedelta(days=1)).isoformat(),
            }
            db.add(
                Listing(
                    owner_id=owner.id, source_url=stale["source_url"], details=stale
                )
            )
            manual = original | {
                "source_url": "https://unit.test/fixture",
                "source_provider": None,
                "last_verified": now.date().isoformat(),
                "rolling": True,
            }
            db.add(
                Listing(
                    owner_id=owner.id, source_url=manual["source_url"], details=manual
                )
            )
            db.commit()
        login = {"email": "isolated@unit.test", "password": "OnlyIsolatedTest@123"}
        assert (
            client.post(
                "/api/auth/register", json=login | {"name": "Isolated user"}
            ).status_code
            == 201
        )
        token = client.post("/api/auth/login", json=login).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert len(client.get("/api/listings", headers=headers).json()) == 1
        endpoint = "/api/applicant/recommendations"
        assert (
            client.get(endpoint, headers=headers).json()["message"]
            == "No currently verified matching internships found."
        )
        assert (
            client.put(
                "/api/applicant/profile",
                headers=headers,
                json={
                    "education": "B.Tech",
                    "academic_branch": "Civil Engineering",
                    "consent": True,
                },
            ).status_code
            == 200
        )
        matched = client.get(endpoint, headers=headers).json()["recommendations"]
        assert [item["listing"]["application_url"] for item in matched] == [URL]
        assert matched[0]["components"]["education"] == 1
