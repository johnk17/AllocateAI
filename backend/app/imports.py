import csv
import io
import json
from pydantic import ValidationError
from sqlalchemy import select
from .schemas import ListingInput, SkillInput
from .db import Listing, Skill, SkillVersion
from .lever_feed import lever_identity


def listing_preview(db, records):
    rows = []
    seen = set()
    existing = set(db.scalars(select(Listing.source_url)))
    existing_lever = {key for url in existing if (key := lever_identity(url))}
    seen_lever = set()
    for index, record in enumerate(records, 1):
        try:
            body = ListingInput.model_validate(record)
            data = body.model_dump(mode="json")
            url = data["source_url"]
            errors = []
            identity = lever_identity(url)
            if url in existing or url in seen or (identity and (identity in existing_lever or identity in seen_lever)):
                errors.append("Duplicate source URL")
            seen.add(url)
            if identity:
                seen_lever.add(identity)
            for requirement in data["requirements"]:
                if not db.get(Skill, requirement["skill_id"]):
                    errors.append(f"Unknown skill ID {requirement['skill_id']}")
                if (
                    requirement["excerpt"]
                    not in data["description"] + "\n" + data["requirements_text"]
                ):
                    errors.append("Requirement excerpt not present in listing text")
            if data["mandatory_qualifications"] and not all(
                q.casefold()
                in (data["description"] + " " + data["requirements_text"]).casefold()
                for q in data["mandatory_qualifications"]
            ):
                errors.append("Mandatory qualification must be stated in source text")
            warnings = [
                f"{key} is unknown"
                for key in (
                    "location",
                    "work_mode",
                    "stipend",
                    "deadline",
                    "last_verified",
                )
                if data.get(key) is None
            ]
            if not data["requirements"]:
                warnings.append(
                    "Technology classifications have not been reviewed; no required skills were invented"
                )
            warnings.append(
                "Capacity is not imported here; confirm seats separately for a specific round"
            )
            rows.append(
                {
                    "row": index,
                    "valid": not errors,
                    "errors": errors,
                    "warnings": warnings,
                    "record": data,
                }
            )
        except ValidationError as exc:
            rows.append(
                {
                    "row": index,
                    "valid": False,
                    "errors": [
                        f"{'.'.join(map(str, e['loc']))}: {e['msg']}"
                        for e in exc.errors()
                    ],
                    "warnings": [],
                    "record": record,
                }
            )
    return {
        "rows": rows,
        "valid_count": sum(r["valid"] for r in rows),
        "error_count": sum(not r["valid"] for r in rows),
    }


def parse_listing_csv(content):
    records = []
    for row in csv.DictReader(io.StringIO(content.decode("utf-8-sig"))):
        for field in ("requirements", "mandatory_qualifications"):
            row[field] = json.loads(row.get(field) or "[]")
        records.append(
            {
                k: (v if v != "" else None)
                for k, v in row.items()
                if k in ListingInput.model_fields
                and not (v == "" and k in {"requirements_text", "status", "rolling"})
            }
        )
    return records


def import_skills(db, rows, source, version):
    added = 0
    updated = 0
    for row in rows:
        if source == "ESCO":
            name = row.get("preferredLabel") or row.get("name")
            cid = row.get("conceptUri") or row.get("canonical_id")
            aliases = (
                (row.get("altLabels") or "").split("\n")
                if isinstance(row.get("altLabels", ""), str)
                else row.get("aliases", [])
            )
            category = row.get("skillType") or row.get("category") or "ESCO skill"
        elif source == "O*NET":
            name = row.get("Example") or row.get("name")
            cid = "onet:" + str(row.get("Commodity Code", "")) + ":" + str(name)
            aliases = []
            category = row.get("Commodity Title") or "O*NET technology"
        else:
            body = SkillInput.model_validate(row)
            name = body.name
            cid = body.canonical_id
            aliases = body.aliases
            category = body.category
        if not name or not cid:
            raise ValueError("Skill name and source identifier are required")
        existing = db.scalar(select(Skill).where(Skill.canonical_id == cid))
        if existing:
            if not db.get(SkillVersion, (existing.id, existing.source_version)):
                db.add(
                    SkillVersion(
                        skill_id=existing.id,
                        source_version=existing.source_version,
                        details={
                            "name": existing.name,
                            "aliases": existing.aliases,
                            "category": existing.category,
                            "source": existing.source,
                        },
                    )
                )
            if version != existing.source_version and not db.get(
                SkillVersion, (existing.id, version)
            ):
                db.add(
                    SkillVersion(
                        skill_id=existing.id,
                        source_version=version,
                        details={
                            "name": name,
                            "aliases": [a for a in aliases if a],
                            "category": category,
                            "source": source,
                        },
                    )
                )
            updated += 1
            continue
        # Source concepts retain distinct canonical IDs; never silently merge related labels.
        db.add(
            Skill(
                canonical_id=cid,
                name=name,
                aliases=[a for a in aliases if a],
                category=category,
                source=source,
                source_version=version,
                related=[],
                reviewed=source in ("ESCO", "O*NET"),
            )
        )
        added += 1
    return {"added": added, "duplicates": updated, "source": source, "version": version}
