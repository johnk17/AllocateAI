"""Download a bounded real ESCO concept sample; preserves URIs and reported version."""

import concurrent.futures, json
from datetime import date
from pathlib import Path
import httpx

BASE = "https://ec.europa.eu/esco/api/search"
terms = [
    "Python",
    "Java",
    "software development",
    "database",
    "machine learning",
    "data analysis",
    "engineering",
    "manufacturing",
    "business",
    "network",
    "cloud",
    "agriculture",
]


def fetch(item):
    term, kind = item
    r = httpx.get(
        BASE,
        params={
            "text": term,
            "type": kind,
            "language": "en",
            "limit": 10,
            "selectedVersion": "v1.2.0",
        },
        follow_redirects=True,
        timeout=60,
    )
    r.raise_for_status()
    return kind, r.json()


rows = {}
occupations = {}
raw = []
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for kind, data in pool.map(
        fetch,
        [(term, "skill") for term in terms]
        + [
            (term, "occupation")
            for term in ["software developer", "data scientist", "mechanical engineer"]
        ],
    ):
        raw.append(data)
        for concept in data.get("_embedded", {}).get("results", []):
            target = occupations if kind == "occupation" else rows
            target[concept["uri"]] = {
                "conceptUri": concept["uri"],
                "preferredLabel": concept.get("preferredLabel", {}).get(
                    "en", concept["title"]
                ),
                "altLabels": "\n".join(
                    concept.get("alternativeLabel", {}).get("en", [])
                ),
                "skillType": "ESCO " + kind,
                "source_payload": concept,
            }
root = Path(__file__).resolve().parents[1] / "data/public"
(root / "esco-import.json").write_text(
    json.dumps(
        {
            "source": "ESCO",
            "version": "API sample requested v1.2.0; retrieved "
            + date.today().isoformat(),
            "rows": list(rows.values()),
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
(root / "esco-occupations.json").write_text(
    json.dumps(
        {
            "source": "ESCO occupations",
            "requested_version": "v1.2.0",
            "retrieved_at": date.today().isoformat(),
            "records": list(occupations.values()),
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(
    f"Downloaded {len(rows)} real skill concepts and {len(occupations)} real occupational concepts. API sample, not the complete ESCO release."
)
