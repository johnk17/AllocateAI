from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx

from app.engine import listing_status
from app.lever_feed import discover, listing_details

ID = "12345678-1234-4123-8123-123456789012"
URL = f"https://jobs.lever.co/hevodata/{ID}"


def test_only_live_form_verifies_and_separate_requirements_are_indexed():
    job = {"id": ID, "text": "Software Engineer Intern", "hostedUrl": URL,
           "applyUrl": URL + "/apply", "categories": {"location": "Bangalore, India"},
           "descriptionPlain": "Join the engineering team.",
           "lists": [{"text": "Qualifications", "content": "<li>Python programming</li>"}],
           "additionalPlain": "Campus recruitment",
           "additional": "<p>Bachelor's degree in <strong>Computer Science</strong></p><ul><li>Experience with <strong>Docker</strong></li></ul>"}
    def respond(request):
        if request.url.host == "api.lever.co":
            return httpx.Response(200, json=[job])
        return httpx.Response(200, headers={"content-type": "text/html"},
                              text='<form id="application-form"></form>')
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        report = discover(client, "hevodata")
    assert len(report.verified) == 1
    row, checked = next(iter(report.verified.values()))
    skill = SimpleNamespace(id=1, name="Python", aliases=[])
    docker = SimpleNamespace(id=2, name="Docker", aliases=[])
    details = listing_details("hevodata", row, checked, [skill, docker])
    assert details["source_skill_names"] == {"1": "Python", "2": "Docker"}
    assert details["source_education"] == ["bachelor's", "computer science"]
    assert listing_status(details) == "open"
    assert listing_status(details | {"source_verified_at": (
        datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()}) == "unverified"

    with httpx.Client(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json=[job]) if req.url.host == "api.lever.co"
        else httpx.Response(200, headers={"content-type": "text/html"}, text="This job is no longer available")
    )) as client:
        unavailable = discover(client, "hevodata")
    assert len(unavailable.internship_candidates) == 1
    assert not unavailable.verified
