"""Import current public internships from explicitly verified Lever employer boards."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from .db import ListingVersion
from .internship_matching import education_terms, published_academics
from .skills import match_skills

BOARDS = {"hevodata": "Hevo Data", "merklescience": "Merkle Science"}
INTERNSHIP = re.compile(r"\b(?:intern(?:ship)?|co[- ]?op)\b", re.I)
FORM = re.compile(r"<form\b[^>]*\bid\s*=\s*['\"]application-form['\"]", re.I)


def lever_identity(url):
    if not isinstance(url, str):
        return None
    try:
        parsed = urlsplit(url)
        parts = parsed.path.strip("/").split("/")
        if parsed.scheme != "https" or parsed.netloc != "jobs.lever.co" or not (
            len(parts) == 2 or len(parts) == 3 and parts[2] == "apply"
        ):
            return None
        return parts[0].lower(), str(UUID(parts[1]))
    except ValueError:
        return None


@dataclass
class Verification:
    board: str
    board_url: str
    fetched: int
    internship_candidates: dict
    verified: dict
    completed: bool


def discover(client, board):
    url = f"https://api.lever.co/v0/postings/{board}?mode=json"
    snapshot = Verification(board, url, 0, {}, {}, False)
    try:
        response = client.get(url)
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("Unexpected board format")
    except (httpx.HTTPError, ValueError):
        return snapshot
    snapshot.fetched = len(rows)
    snapshot.completed = True
    for row in rows:
        title = row.get("text") or ""
        category = row.get("categories") or {}
        if not (INTERNSHIP.search(title) or INTERNSHIP.fullmatch(category.get("commitment") or "")):
            continue
        hosted, apply = row.get("hostedUrl"), row.get("applyUrl")
        key = lever_identity(hosted)
        if not key or key != (board, row.get("id")):
            continue
        snapshot.internship_candidates[key] = row
        if not title or not row.get("descriptionPlain") or lever_identity(apply) != key:
            continue
        # Only query the exact HTTPS job application path on the known provider. Do not follow redirects.
        if urlsplit(apply).path != f"/{board}/{key[1]}/apply":
            continue
        try:
            page = client.get(apply, follow_redirects=False)
            if page.status_code != 200 or "text/html" not in page.headers.get("content-type", "") or not FORM.search(page.text):
                continue
        except httpx.HTTPError:
            continue
        snapshot.verified[key] = (row, datetime.now(timezone.utc))
    return snapshot


def posting_text(html, plain=""):
    if not html:
        return plain or ""
    html = re.sub(r"(?is)<(?:script|style)\b[^>]*>.*?</(?:script|style)>", "", html)
    html = re.sub(r"(?i)</(?:li|p|div|h[1-6])>|<br\s*/?>", "\n", html)
    return unescape(re.sub(r"<[^>]+>", "", html)).strip() or plain or ""


def listing_details(board, row, verified_at, skill_catalog):
    category = row.get("categories") or {}
    # Lever's HTML can contain employer-written text missing from the plain-text projection.
    sections = [posting_text(row.get("description"), row.get("descriptionPlain"))]
    requirements = []
    for item in row.get("lists") or []:
        heading, body = item.get("text") or "", posting_text(item.get("content"))
        if re.search(r"qualifications|requirements|what you bring|who you are|what you need|skills", heading, re.I):
            requirements.append(body)
        sections.extend((heading, body))
    sections.append(posting_text(row.get("additional"), row.get("additionalPlain")))
    description = "\n".join(section.strip() for section in sections if section.strip())[:30000]
    requirements_text = "\n".join(requirements) or "\n".join(
        line for line in description.splitlines()
        if re.search(r"\b(?:degree|bachelor|master|qualifications|proficiency)\b", line, re.I)
    )
    details = {
        "title": row["text"][:200], "organization": BOARDS[board],
        "source_name": "Lever employer board", "source_provider": "lever",
        "source_board": board, "source_posting_id": row["id"],
        "source_board_url": f"https://jobs.lever.co/{board}",
        "source_url": row["hostedUrl"], "application_url": row["applyUrl"],
        "source_verified_at": verified_at.isoformat(),
        "last_verified": verified_at.date().isoformat(),
        "source_approved": True, "status": "open", "rolling": False, "deadline": None,
        "location": category.get("location"), "sector": None,
        "work_mode": {"on-site": "onsite", "onsite": "onsite", "hybrid": "hybrid", "remote": "remote"}.get(
            (row.get("workplaceType") or "").lower()),
        "description": description, "requirements_text": requirements_text[:20000], "stipend": None,
        "mandatory_qualifications": [],
    }
    return details | index_listing(details, skill_catalog) | {"source_education": sorted(education_terms(description))}


def index_listing(details, skill_catalog):
    text = "\n".join((details["requirements_text"], details["description"]))
    hits = match_skills(text, skill_catalog)
    hits = [hit for hit in hits if hit["value"] != "Go" or not re.search(
        r"\bgo[- ]to[- ]market\b", hit["excerpt"], re.I)]
    fields, education = published_academics(details["title"], details["requirements_text"])
    return {
        "requirements": [{"skill_id": hit["skill_id"], "classification": "mentioned", "excerpt": hit["excerpt"]} for hit in hits],
        "source_skill_names": {str(hit["skill_id"]): hit["value"] for hit in hits},
        "source_education": education,
        "academic_fields": fields,
    }


def save_listing_version(db, listing, details):
    # A timestamp refresh is not a content revision.
    hidden = {"last_verified", "source_verified_at", "source_last_checked_at", "listing_version"}
    before = {k: v for k, v in listing.details.items() if k not in hidden}
    after = {k: v for k, v in details.items() if k not in hidden}
    version = listing.details.get("listing_version", 0)
    if before != after:
        version += 1
        db.add(ListingVersion(listing_id=listing.id, version=version, details=details | {"listing_version": version}))
    listing.details = details | {"listing_version": version}
