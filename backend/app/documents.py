from zipfile import ZipFile
import io
from docx import Document as DocxDocument
import pymupdf
from sqlalchemy import select
from .db import Evidence, Skill
from .skills import match_skills, exact_skill, claim_supported


def parse_document(content, extension):
    if extension == ".pdf":
        with pymupdf.open(stream=content, filetype="pdf") as doc:
            if doc.is_encrypted or len(doc) > 30:
                raise ValueError("Use an unencrypted PDF of at most 30 pages")
            return [{"page": n + 1, "text": p.get_text()} for n, p in enumerate(doc)]
    if extension == ".docx":
        with ZipFile(io.BytesIO(content)) as package:
            entries = package.infolist()
            if len(entries) > 500 or sum(e.file_size for e in entries) > 40_000_000:
                raise ValueError("Expanded document exceeds safe limits")
        doc = DocxDocument(io.BytesIO(content))
        return [
            {
                "page": 1,
                "text": "\n".join(p.text for p in doc.paragraphs)
                + "\n"
                + "\n".join(
                    " | ".join(c.text for c in r.cells)
                    for t in doc.tables
                    for r in t.rows
                ),
            }
        ]
    raise ValueError("Only PDF and DOCX are supported")


def extract_document(db, document, provider, name, allow_hosted=False):
    skills = db.scalars(select(Skill).where(Skill.merged_into.is_(None))).all()
    use_model = provider.mode == "live" and allow_hosted
    provider_failed = False
    if use_model:
        try:
            if not provider.qualify():
                raise ValueError("Configured provider did not pass a capability check")
            claims = [
                c.model_dump() for c in provider.extract(document.pages, name).claims
            ]
        except Exception:
            provider_failed = True
            use_model = False
    if not use_model:
        claims = [
            {"kind": "skill", **hit, "page": p["page"]}
            for p in document.pages
            for hit in match_skills(p["text"], skills)
        ]
    added = 0
    unsupported = 0
    for claim in claims:
        page = next(
            (p["text"] for p in document.pages if p["page"] == claim["page"]), ""
        )
        if claim["excerpt"] not in page:
            unsupported += 1
            continue  # Unsupported LLM quote is not stored as evidence.
        skill = (
            exact_skill(claim["value"], skills) if claim["kind"] == "skill" else None
        )
        supported = claim_supported(
            claim["kind"], claim["value"], claim["excerpt"], skill
        )
        status = "suggested" if supported else "needs_review"
        db.add(
            Evidence(
                applicant_id=document.owner_id,
                document_id=document.id,
                kind=claim["kind"],
                value=skill.name if skill else claim["value"],
                skill_id=skill.id if skill else None,
                excerpt=claim["excerpt"],
                section=claim.get("context", "mentioned"),
                page=claim["page"],
                source="resume",
                context=claim.get("context", "mentioned"),
                status=status,
            )
        )
        added += 1
    return {
        "claims_stored": added,
        "unsupported_claims_discarded": unsupported,
        "mode": "live" if use_model else "fixture",
        "provider_unavailable": provider_failed,
        "manual_entry_required": not any(p["text"].strip() for p in document.pages),
    }
