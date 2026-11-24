"""Refresh original India internship postings without creating allocation capacity."""

import json
import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from html import unescape
from urllib.parse import urlencode

import httpx
from sqlalchemy import select

from .db import Listing, Skill, State, User, utcnow
from .internship_matching import is_managed
from .lever_feed import (
    BOARDS,
    FORM,
    INTERNSHIP,
    discover,
    index_listing,
    lever_identity,
    listing_details,
    posting_text,
    save_listing_version,
)

LOG = logging.getLogger(__name__)
SWAYAM = "https://swayamplus.education.gov.in"
SWAYAM_PATH = re.compile(r"/internships/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})")
GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards"
GREENHOUSE_BOARDS = {
    "stripe": ("Stripe", {"Stripe"}),
    "rubrik": ("Rubrik", {"Rubrik", "Rubrik Job Board"}),
    "inmobi": ("InMobi", {"InMobi"}),
}
INDIA = re.compile(
    r"\b(?:india|bengaluru|bangalore|chennai|hyderabad|mumbai|pune|delhi|noida|"
    r"gurgaon|gurugram|kolkata|ahmedabad|kochi|coimbatore|jaipur|chandigarh|indore)\b",
    re.IGNORECASE,
)
QUALIFICATION_HEADINGS = re.compile(
    r"requirements|qualifications|what you(?:'ll| will) need|what you bring|what you have",
    re.IGNORECASE,
)
JOB_SCRIPT = re.compile(
    r'<script\b[^>]*\btype="application/ld\+json"[^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
APPLY_BUTTON = re.compile(r"<button\b([^>]*)>\s*Apply Now\b", re.IGNORECASE)
DATE_COUNT = re.compile(
    r"Showing\s+(\d+)\s*-\s*(\d+)\s+of\s+(\d+)\s+internships", re.IGNORECASE
)


@dataclass
class BoardResult:
    provider: str
    board: str
    url: str
    fetched: int = 0
    completed: bool = False
    candidates: set = field(default_factory=set)
    verified: dict = field(default_factory=dict)
    issues: Counter = field(default_factory=Counter)


def checked_html(client, url):
    response = client.get(url, follow_redirects=False)
    response.raise_for_status()
    if "text/html" not in response.headers.get("content-type", "").lower():
        raise ValueError("Expected a public HTML page")
    return response.text


def _timestamp(value):
    if value:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("Expected a timestamp with an offset")
        return parsed
    return None


def _sections(html, heading_matches):
    pattern = r"<h[2-5]\b[^>]*>(.*?)</h[2-5]>(.*?)(?=<h[2-5]\b|</section>|\Z)"
    return "\n".join(
        posting_text(body)
        for heading, body in re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
        if heading_matches(posting_text(heading))
    )


def _details(
    result,
    key,
    title,
    organization,
    source,
    apply,
    location,
    description,
    requirements,
    checked,
    work_mode=None,
    stipend=None,
    closes=None,
):
    return {
        "source_provider": result.provider,
        "source_board": result.board,
        "source_name": {
            "greenhouse": "Greenhouse employer board",
            "swayam-plus": "SWAYAM Plus",
        }[result.provider],
        "source_board_url": result.url,
        "source_posting_id": key,
        "source_url": source,
        "application_url": apply,
        "source_verified_at": checked.isoformat(),
        "last_verified": checked.date().isoformat(),
        "source_closes_at": closes.isoformat() if closes else None,
        "deadline": closes.date().isoformat() if closes else None,
        "source_approved": True,
        "status": "open",
        "rolling": False,
        "title": title[:200],
        "organization": organization[:200],
        "location": location[:200],
        "description": description[:30000],
        "requirements_text": requirements[:20000],
        "stipend": stipend,
        "work_mode": work_mode,
        "sector": None,
        "mandatory_qualifications": [],
    }


def _greenhouse_posting(client, result, job, organization, names):
    key = str(job["id"])
    api_url = f"{GREENHOUSE}/{result.board}/jobs/{key}"
    detail = client.get(api_url, params={"questions": "true"}).raise_for_status().json()
    if (
        str(detail.get("id")) != key
        or detail.get("company_name") not in names
        or detail.get("title") != job["title"]
        or not detail.get("internal_job_id")
        or not detail.get("questions")
    ):
        raise ValueError("Posting identity or application fields missing")
    closes = _timestamp(detail.get("application_deadline"))
    if closes and closes <= utcnow():
        raise ValueError("Published deadline passed")
    # Greenhouse's own listing-specific application form remains reachable for custom boards.
    query = urlencode({"for": result.board, "token": key})
    apply = f"https://job-boards.greenhouse.io/embed/job_app?{query}"
    form = checked_html(client, apply)
    page_title = re.search(r"<title>(.*?)</title>", form, re.IGNORECASE | re.DOTALL)
    if (
        not FORM.search(form)
        or not page_title
        or not posting_text(page_title[1]).startswith(
            f"Job Application for {job['title']} at "
        )
        or f'action="/embed/job_app?{query}"' not in unescape(form)
    ):
        raise ValueError("Listing-specific application form unavailable")
    content = unescape(detail.get("content") or "")
    description = posting_text(content)
    if len(description) < 10:
        raise ValueError("Employer description missing")
    requirements = _sections(content, QUALIFICATION_HEADINGS.search)
    return _details(
        result,
        key,
        job["title"],
        organization,
        apply,
        apply,
        job["location"]["name"],
        description,
        requirements,
        utcnow(),
        closes=closes,
    ) | {
        "source_record_url": api_url,
    }


def greenhouse(client, board, organization, names):
    result = BoardResult("greenhouse", board, f"{GREENHOUSE}/{board}/jobs")
    try:
        payload = client.get(result.url).raise_for_status().json()
        rows = payload["jobs"]
        if not isinstance(rows, list) or payload["meta"]["total"] != len(rows):
            raise ValueError("Incomplete job board response")
        candidates = [
            row
            for row in rows
            if isinstance(row.get("id"), int)
            and INTERNSHIP.search(row.get("title") or "")
            and INDIA.search((row.get("location") or {}).get("name") or "")
        ]
    except (httpx.HTTPError, KeyError, ValueError, TypeError, AttributeError) as exc:
        result.issues[f"Board unavailable ({type(exc).__name__})"] += 1
        return result
    result.fetched = len(rows)
    result.completed = True
    for job in candidates:
        key = str(job["id"])
        result.candidates.add(key)
        try:
            result.verified[key] = _greenhouse_posting(
                client, result, job, organization, names
            )
        except (
            httpx.HTTPError,
            KeyError,
            ValueError,
            TypeError,
            AttributeError,
        ) as exc:
            result.issues[
                str(exc) if type(exc) is ValueError else type(exc).__name__
            ] += 1
    return result


def _swayam_posting(client, result, key):
    url = f"{SWAYAM}/internships/{key}"
    html = checked_html(client, url)
    for script in JOB_SCRIPT.findall(html):
        job = json.loads(script)
        if isinstance(job, dict) and job.get("@type") == "JobPosting":
            break
    else:
        raise ValueError("Structured posting missing")
    organization = job.get("hiringOrganization", {}).get("name", "").strip()
    description = job.get("description", "").strip()
    title = job.get("title", "").strip()
    closes = _timestamp(job.get("validThrough"))
    checked = utcnow()
    if not closes or checked >= closes:
        raise ValueError("Missing or expired deadline")
    if (
        job.get("employmentType") != "INTERN"
        or not title
        or not organization
        or len(description) < 10
    ):
        raise ValueError("Published employer or internship details missing")
    if not any(
        not re.search(
            r"(?:\sdisabled(?:\s|=|$)|\saria-disabled\s*=\s*['\"]true)",
            attrs,
            re.IGNORECASE,
        )
        for attrs in APPLY_BUTTON.findall(html)
    ):
        raise ValueError("Apply control unavailable")
    address = (job.get("jobLocation") or {}).get("address") or {}
    if address.get("addressCountry") == "IN":
        location = ", ".join(
            filter(
                None,
                (address.get("addressLocality"), address.get("addressRegion"), "India"),
            )
        )
    elif job.get("jobLocationType") == "TELECOMMUTE" and not address:
        location = "Remote (India)"
    else:
        raise ValueError("India location unavailable")
    mode = re.search(
        r'"mode"\s*:\s*"(ON_SITE|HYBRID|REMOTE)"', html.replace(r"\"", '"')
    )
    work_mode = (
        {"ON_SITE": "onsite", "HYBRID": "hybrid", "REMOTE": "remote"}.get(mode[1])
        if mode
        else None
    )
    sections = _sections(
        html, lambda heading: heading in {"Requirements", "Skills required"}
    )
    duties = _sections(html, lambda heading: heading == "What you'll do")
    if duties:
        description += "\n\n" + duties
    salary = job.get("baseSalary") or {}
    value = salary.get("value") or {}
    stipend = (
        f"{salary['currency']} {value['value']} / month"
        if salary.get("currency") == "INR"
        and value.get("unitText") == "MONTH"
        and isinstance(value.get("value"), (int, float))
        else None
    )
    return _details(
        result,
        key,
        title,
        organization,
        url,
        url,
        location,
        description,
        sections,
        checked,
        work_mode,
        stipend,
        closes,
    )


def swayam(client):
    result = BoardResult("swayam-plus", "swayam-plus", f"{SWAYAM}/internships")
    total = 0
    page_total = 1
    try:
        for page in range(1, 51):
            url = result.url if page == 1 else f"{result.url}?page={page}"
            html = checked_html(client, url)
            count = DATE_COUNT.search(posting_text(html))
            if not count:
                raise ValueError("Public directory count missing")
            first, last, advertised = map(int, count.groups())
            keys = set(re.findall(r'href="' + SWAYAM_PATH.pattern + r'"', html))
            if page == 1:
                total = advertised
            if (
                first != page_total
                or advertised != total
                or len(keys) != last - first + 1
                or keys & result.candidates
            ):
                raise ValueError("Public directory pagination changed")
            result.candidates.update(keys)
            page_total = last + 1
            if last == total:
                result.completed = True
                break
        if not result.completed:
            raise ValueError("Public directory exceeded the configured page limit")
    except (httpx.HTTPError, ValueError) as exc:
        result.issues[str(exc) if type(exc) is ValueError else type(exc).__name__] += 1
    result.fetched = len(result.candidates)

    def verify(key):
        try:
            return key, _swayam_posting(client, result, key), None
        except (
            httpx.HTTPError,
            KeyError,
            ValueError,
            TypeError,
            AttributeError,
        ) as exc:
            return (
                key,
                None,
                str(exc) if type(exc) is ValueError else type(exc).__name__,
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        for key, details, issue in pool.map(verify, sorted(result.candidates)):
            if details:
                result.verified[key] = details
            else:
                result.issues[issue] += 1
    return result


def _lever(client, board):
    snapshot = discover(client, board)
    result = BoardResult(
        "lever", board, snapshot.board_url, snapshot.fetched, snapshot.completed
    )
    result.candidates = {key[1] for key in snapshot.internship_candidates}
    for key, (row, when) in snapshot.verified.items():
        all_locations = [
            row.get("categories", {}).get("location") or "",
            *row.get("categories", {}).get("allLocations", []),
        ]
        local = sorted(
            {location for location in all_locations if INDIA.search(location)}
        )
        if local:
            details = listing_details(board, row, when, [])
            result.verified[key[1]] = details | {
                "source_locations": local,
                "location": "; ".join(local),
            }
        else:
            result.issues["No published India location"] += 1
    if not result.completed:
        result.issues["Board unavailable"] += 1
    elif missing := len(result.candidates) - len(snapshot.verified):
        result.issues["Application page could not be verified"] += missing
    return result


def _identity(details):
    return (
        details.get("source_provider"),
        details.get("source_board"),
        details.get("source_posting_id"),
    )


def sync(session_factory):
    started = utcnow()
    with (
        httpx.Client(
            timeout=15,
            follow_redirects=False,
            headers={"User-Agent": "AllocateAI public internship verifier"},
        ) as client,
        ThreadPoolExecutor(max_workers=6) as pool,
    ):
        tasks = [pool.submit(_lever, client, board) for board in BOARDS]
        tasks += [
            pool.submit(greenhouse, client, board, *employer)
            for board, employer in GREENHOUSE_BOARDS.items()
        ]
        tasks.append(pool.submit(swayam, client))
        results = [task.result() for task in tasks]

    with session_factory() as db:
        db.get(State, 1, with_for_update=True)
        owner = db.scalar(
            select(User.id).where(User.role == "admin").order_by(User.id).limit(1)
        )
        if owner is None:
            raise RuntimeError(
                "An existing administrator must own public listing records"
            )
        skills = [
            skill
            for skill in db.scalars(
                select(Skill).where(
                    Skill.canonical_id.like("curated:%"), Skill.merged_into.is_(None)
                )
            )
            if len(skill.name) > 1
        ]
        listings = list(db.scalars(select(Listing)))
        by_url = {listing.source_url: listing for listing in listings}
        lever_urls = {
            key: listing
            for listing in listings
            if (key := lever_identity(listing.source_url))
        }
        managed = {
            _identity(listing.details): listing
            for listing in listings
            if is_managed(listing.details)
        }
        report = []

        for result in results:
            counts = Counter(inserted=0, updated=0, withdrawn=0, manual_duplicates=0)
            coverage = Counter()
            for key, details in result.verified.items():
                identity = (result.provider, result.board, key)
                url = details["source_url"]
                collision = by_url.get(url) or (
                    lever_urls.get((result.board, key))
                    if result.provider == "lever"
                    else None
                )
                listing = managed.get(identity)
                if collision is not None and collision is not listing:
                    counts["manual_duplicates"] += 1
                    continue
                if listing and _newer_than(listing, started):
                    continue
                if listing is None:
                    listing = Listing(owner_id=owner, source_url=url, details={})
                    db.add(listing)
                    db.flush()
                    by_url[url] = listing
                    counts["inserted"] += 1
                else:
                    listing.source_url = url
                    counts["updated"] += 1
                details |= index_listing(details, skills) | {
                    "source_last_checked_at": started.isoformat()
                }
                save_listing_version(db, listing, details)
                coverage.update(
                    details["academic_fields"] or ["Other / no explicit field"]
                )

            for (provider, board, key), listing in managed.items():
                if (
                    (provider, board) != (result.provider, result.board)
                    or key in result.verified
                    or _newer_than(listing, started)
                ):
                    continue
                status = (
                    "expired"
                    if result.completed and key not in result.candidates
                    else "unverified"
                )
                if listing.details.get("status") == "open":
                    counts["withdrawn"] += 1
                save_listing_version(
                    db,
                    listing,
                    listing.details
                    | {
                        "status": status,
                        "source_approved": False,
                        "source_last_checked_at": started.isoformat(),
                    },
                )
            report.append(
                {
                    "provider": result.provider,
                    "board": result.board,
                    "source": result.url,
                    "board_fetched": result.completed,
                    "postings_fetched": result.fetched,
                    "internships_fetched": len(result.candidates),
                    "verified": len(result.verified),
                    "coverage": dict(sorted(coverage.items())),
                    "issues": dict(result.issues),
                    **counts,
                }
            )
        db.commit()
    return report


def _newer_than(listing, started):
    checked = listing.details.get("source_last_checked_at")
    return bool(checked and datetime.fromisoformat(checked) > started)
