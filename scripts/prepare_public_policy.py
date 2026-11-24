"""Convert the downloaded, dated public PIB reference to an admin import payload."""

import json, re
from pathlib import Path
import pymupdf

root = Path(__file__).resolve().parents[1]
path = root / "data/public/pmis-pilot-2024-10-11.pdf"
with pymupdf.open(path) as doc:
    sections = {
        f"Page {n + 1}": page.get_text().strip()
        for n, page in enumerate(doc)
        if page.get_text().strip()
    }
payload = {
    "title": "Skilling India: Empowering the Workforce (PIB, 11 October 2024)",
    "scope": "Historical skilling initiatives and 2024-25 PMIS pilot (launched 2024-10-03); not current eligibility or confirmed internship listings",
    "effective_date": "2024-10-03",
    "version": "PIB publication 2024-10-11; historical reference",
    "source_url": "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2024/oct/doc20241011415001.pdf",
    "sections": sections,
}
(root / "data/public/policy-import.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(
    "Prepared",
    len(sections),
    "dated public-reference sections. No enforcement rules inferred.",
)
print("\n".join(f"{key}: {len(value)} characters" for key, value in sections.items()))
