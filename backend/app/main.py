import asyncio
import csv
import io
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager, ExitStack, contextmanager, suppress
from datetime import date, timedelta, timezone
from pathlib import Path
from threading import RLock
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, delete, func, text
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from .db import *
from . import schemas as S
from .security import hash_password, verify_password, token_hash
from .skills import install_curated, claim_supported, match_skills
from .documents import parse_document, extract_document
from .llm import Provider
from .retrieval import Embedder, answer, evaluate, MODEL
from .engine import (
    optimize,
    verify_draft,
    fingerprint,
    pairs_for,
    listing_status,
    score,
)
from .services import applicant_snapshot, round_snapshot, unresolved_case
from .agent import build_graph, graph_config
from .imports import listing_preview, parse_listing_csv, import_skills
from .evaluation import extraction_evaluation
from .internship_matching import is_managed, relevant_match
from .lever_feed import lever_identity
from .public_feed import LOG as feed_log, sync as sync_public


NO_MATCHES = "No currently verified matching internships found."


def create_app(
    database_url=None, test=False, checkpointer=None, embedder=None, provider=None
):
    local_sqlite = os.getenv("ALLOCATEAI_LOCAL_SQLITE") == "1" and not test
    isolated_fixtures = test or (local_sqlite and os.getenv("ALLOCATEAI_E2E_FIXTURES") == "1")
    if local_sqlite:
        database_url = database_url or os.getenv("DATABASE_URL")
        if not database_url or not database_url.startswith("sqlite:///"):
            raise RuntimeError(
                "Local mode requires a new, explicit SQLite DATABASE_URL"
            )
        db_path = database_url.removeprefix("sqlite:///")
        if (
            Path(db_path).resolve()
            == (Path(__file__).resolve().parents[2] / "allocateai.db").resolve()
        ):
            raise RuntimeError(
                "The legacy database is read-only to this application. Use a different DB."
            )
    engine, Session = database(database_url, test=test or local_sqlite)
    embedder = embedder or Embedder()
    provider = provider or Provider()
    local_lock = RLock()
    uploads = Path(
        os.getenv(
            "UPLOAD_DIR",
            str(Path(__file__).resolve().parents[2] / "private" / "uploads"),
        )
    )
    uploads.mkdir(parents=True, exist_ok=True)

    async def refresh_employer_listings():
        while True:
            try:
                feed_log.info("Public internship refresh: %s", await asyncio.to_thread(sync_public, Session))
            except Exception:
                feed_log.exception("Public internship refresh failed")
            await asyncio.sleep(4 * 60 * 60)

    @asynccontextmanager
    async def lifespan(app):
        with ExitStack() as stack:
            saver = checkpointer
            if saver is None:
                if test or local_sqlite:
                    saver = InMemorySaver()
                else:
                    url = os.getenv("CHECKPOINT_URL") or str(
                        engine.url.render_as_string(hide_password=False)
                    ).replace("postgresql+psycopg://", "postgresql://")
                    saver = stack.enter_context(PostgresSaver.from_conn_string(url))
                    saver.setup()
            app.state.saver = saver
            app.state.graph = build_graph(Session, provider, embedder, saver)
            with Session() as db:
                if not db.get(State, 1):
                    db.add(State(id=1, revision=1))
                email = os.getenv("ADMIN_EMAIL", "admin@allocate.local").lower()
                if not db.scalar(select(User).where(User.email == email)):
                    password = os.getenv("ADMIN_PASSWORD")
                    if not password or len(password) < 10:
                        raise RuntimeError("Set an ADMIN_PASSWORD of at least 10 characters to bootstrap the local administrator")
                    db.add(
                        User(
                            email=email,
                            name="Placement administrator",
                            role="admin",
                            password_hash=hash_password(password),
                        )
                    )
                install_curated(db)
                db.commit()
            task = None
            if not test and engine.dialect.name == "postgresql" and os.getenv(
                "PUBLIC_INTERNSHIP_SYNC_ENABLED", os.getenv("LEVER_SYNC_ENABLED", "1")
            ) == "1":
                task = asyncio.create_task(refresh_employer_listings())
            try:
                yield
            finally:
                if task:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
        engine.dispose()

    app = FastAPI(
        title="AllocateAI Agentic Internship Matching",
        version="2.0.0",
        lifespan=lifespan,
        description="Independent academic project. Real-data import required. Fixture mode is not live LLM evaluation.",
    )
    app.state.Session = Session
    app.state.engine = engine
    app.state.embedder = embedder
    app.state.provider = provider
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    bearer = HTTPBearer(auto_error=False)

    def get_db():
        with Session() as db:
            yield db

    def current(
        credentials: HTTPAuthorizationCredentials = Depends(bearer), db=Depends(get_db)
    ):
        session = (
            db.get(LoginSession, token_hash(credentials.credentials))
            if credentials
            else None
        )
        if not session or session.expires_at.replace(tzinfo=timezone.utc) <= utcnow():
            raise HTTPException(401, "Sign in with a valid session")
        user = db.get(User, session.user_id)
        if not user or (
            user.role in ("company", "placement") and not db.get(StaffGrant, user.id)
        ):
            raise HTTPException(
                403, "Staff account requires administrator verification"
            )
        return user

    def roles(*allowed):
        def required(user=Depends(current)):
            if user.role not in allowed:
                raise HTTPException(403, "This role cannot perform that action")
            return user

        return required

    def audit(db, actor, action, entity, entity_id):
        db.add(
            AuditEvent(
                actor_id=actor.id, action=action, entity=entity, entity_id=entity_id
            )
        )

    def scoped_staff(db, user, scope):
        grant = db.get(StaffGrant, user.id)
        if (
            not grant
            or grant.role != user.role
            or grant.scope.casefold() != scope.casefold()
        ):
            raise HTTPException(
                403, "Verified staff membership for this scope is required"
            )
        return grant

    def controlled_round(db, rid, collecting=False):
        row = db.get(RoundControl, rid)
        if not row:
            raise HTTPException(409, "Round needs an approved role scope")
        if collecting and row.snapshot is not None:
            raise HTTPException(
                409, "Choices and seats are closed for this frozen round"
            )
        return row

    def record_version(db, listing, details):
        prior = listing.details or {}
        version = prior.get("listing_version", 1 if prior else 0) + 1
        if (
            prior
            and not db.get(ListingVersion, (listing.id, version - 1))
            and version > 1
        ):
            db.add(
                ListingVersion(
                    listing_id=listing.id, version=version - 1, details=prior
                )
            )
        listing.details = details | {"listing_version": version}
        db.add(
            ListingVersion(
                listing_id=listing.id, version=version, details=listing.details
            )
        )

    def user_json(u):
        return {"id": u.id, "name": u.name, "email": u.email, "role": u.role}

    def owned(row, user, owner="owner_id"):
        if not row or (user.role != "admin" and getattr(row, owner) != user.id):
            raise HTTPException(404, "Record not found")
        return row

    def listing_json(row):
        return {
            "id": row.id,
            "owner_id": row.owner_id,
            **{
                key: value
                for key, value in row.details.items()
                if key in S.ListingInput.model_fields
            },
            "declared_status": row.details.get("status", "unverified"),
            "status": listing_status(row.details),
            "listing_version": row.details.get("listing_version", 1),
            **{key: row.details[key] for key in ("application_url", "source_provider", "source_verified_at",
                                                "source_last_checked_at", "source_closes_at", "academic_fields", "source_board_url")
               if key in row.details},
        }

    def student_open_listing(row):
        return (is_managed(row.details) or isolated_fixtures) and listing_status(row.details) == "open"

    def skill_json(row):
        return {
            k: getattr(row, k)
            for k in (
                "id",
                "canonical_id",
                "name",
                "aliases",
                "category",
                "source",
                "source_version",
                "related",
                "reviewed",
                "merged_into",
            )
        }

    def evidence_json(row):
        return {
            k: getattr(row, k)
            for k in (
                "id",
                "applicant_id",
                "document_id",
                "kind",
                "value",
                "skill_id",
                "excerpt",
                "section",
                "page",
                "source",
                "context",
                "status",
                "reviewed_by",
                "review_note",
            )
        }

    def case_json(case, db):
        activities = db.scalars(
            select(Activity).where(Activity.case_id == case.id).order_by(Activity.id)
        ).all()
        snap = app.state.graph.get_state(graph_config(case.id))
        return {
            "id": case.id,
            "applicant_id": case.applicant_id,
            "round_id": case.round_id,
            "policy_id": case.policy_id,
            "status": case.status,
            "mode": case.mode,
            "next_nodes": list(snap.next),
            "unresolved": unresolved_case(db, case),
            "activity": [
                {
                    "id": a.id,
                    "step": a.step,
                    "tool": a.tool,
                    "outcome": a.outcome,
                    "next_action": a.next_action,
                    "at": a.created_at.isoformat(),
                }
                for a in activities
            ],
        }

    @contextmanager
    def thread_lock(thread_id):
        if engine.dialect.name == "postgresql":
            with engine.connect() as connection:
                connection.execute(
                    text("SELECT pg_advisory_lock(hashtext(:id))"), {"id": thread_id}
                )
                try:
                    yield
                finally:
                    connection.execute(
                        text("SELECT pg_advisory_unlock(hashtext(:id))"),
                        {"id": thread_id},
                    )
                    connection.commit()
        else:
            with local_lock:
                yield

    def draft_json(d, db):
        return {
            "id": d.id,
            "round_id": d.round_id,
            "policy_version": d.policy_id,
            "revision": d.revision,
            "stale": d.revision != revision(db),
            "digest": d.digest,
            "approved_by": d.approved_by,
            "published_at": d.published_at.replace(tzinfo=timezone.utc).isoformat()
            if d.published_at
            else None,
            **{k: v for k, v in d.result.items() if k != "input_snapshot"},
        }

    def check_draft(d, db):
        if not d:
            raise HTTPException(404, "Draft not found")
        if d.revision != revision(db):
            raise HTTPException(
                409, "Inputs changed. Rerun allocation and approve the new exact draft."
            )
        policy = db.get(Policy, d.policy_id)
        if not policy.approved_by or db.get(Round, d.round_id).policy_id != d.policy_id:
            raise HTTPException(409, "Policy approval/version mismatch")
        if fingerprint(d.result) != d.digest:
            raise HTTPException(409, "Draft integrity check failed")
        control = controlled_round(db, d.round_id)
        try:
            members, roles_in_round, fresh_policy = round_snapshot(db, d.round_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        current_snapshot = {
            "applicants": members,
            "listings": roles_in_round,
            "rules": fresh_policy.config
            | {"policy_version": fresh_policy.id, "tie_seed": control.tie_seed},
        }
        if (
            d.result.get("input_hash") != control.snapshot_hash
            or d.result.get("input_hash") != fingerprint(current_snapshot)
            or d.result.get("input_hash") != fingerprint(d.result.get("input_snapshot"))
            or d.result.get("output_hash") != fingerprint(d.result["placements"])
        ):
            raise HTTPException(409, "Frozen input or draft output digest changed")
        errors = verify_draft(d.result)
        if errors:
            raise HTTPException(409, {"deterministic_checks": errors})

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/api/health", tags=["System"])
    def health():
        return {
            "status": "ok",
            "version": "2.0.0",
            "llm_mode": provider.mode,
            "fixture_mode": provider.mode == "fixture",
            "embedding_status": embedder.detail,
            "database": engine.dialect.name,
            "checkpoints": "memory" if test or local_sqlite else "postgresql",
            "official_portal": False,
        }

    @app.post("/api/auth/register", status_code=201, tags=["Auth"])
    def register(body: S.Register, db=Depends(get_db)):
        revision(db, True)
        existing = db.scalar(select(User).where(User.email == body.email.lower()))
        if existing:
            invite = (
                db.get(Invitation, token_hash(body.activation_token))
                if body.activation_token
                else None
            )
            if (
                not invite
                or invite.user_id != existing.id
                or existing.role != "applicant"
                or body.role != "applicant"
                or invite.expires_at.replace(tzinfo=timezone.utc) <= utcnow()
            ):
                raise HTTPException(
                    409,
                    "Email already registered. Imported participants need their administrator-issued activation token.",
                )
            existing.password_hash = hash_password(body.password)
            existing.name = body.name
            db.delete(invite)
            db.commit()
            return user_json(existing)
        user = User(
            name=body.name,
            email=body.email.lower(),
            role=body.role,
            password_hash=hash_password(body.password),
        )
        db.add(user)
        db.flush()
        if user.role == "applicant":
            db.add(Profile(user_id=user.id, details=S.ProfileInput().model_dump()))
        db.commit()
        return user_json(user)

    @app.get("/api/staff/status", tags=["Auth"])
    def staff_status(user=Depends(current), db=Depends(get_db)):
        request = db.get(StaffRequest, user.id)
        grant = db.get(StaffGrant, user.id)
        return {
            "requested": bool(request),
            "verified": bool(grant and grant.role == user.role),
            "scope": grant.scope if grant else request.scope if request else None,
        }

    @app.post("/api/staff/request", tags=["Auth"])
    def request_staff(
        body: S.StaffRequestInput, user=Depends(roles("applicant")), db=Depends(get_db)
    ):
        db.merge(StaffRequest(user_id=user.id, **body.model_dump()))
        db.commit()
        return {"requested": True}

    @app.get("/api/admin/staff/requests", tags=["Auth"])
    def staff_requests(user=Depends(roles("admin")), db=Depends(get_db)):
        return [
            {
                "user_id": row.user_id,
                "scope": row.scope,
                "reference": row.evidence_reference,
            }
            for row in db.scalars(select(StaffRequest).order_by(StaffRequest.user_id))
        ]

    @app.put("/api/admin/staff/{uid}", tags=["Auth"])
    def grant_staff(
        uid: int,
        body: S.StaffGrantInput,
        user=Depends(roles("admin")),
        db=Depends(get_db),
    ):
        revision(db, True)
        target = db.get(User, uid)
        if not target or target.role == "admin":
            raise HTTPException(404, "Eligible staff account not found")
        db.merge(
            StaffGrant(
                user_id=uid,
                approved_by=user.id,
                approved_at=utcnow(),
                **body.model_dump(),
            )
        )
        target.role = body.role
        db.execute(delete(StaffRequest).where(StaffRequest.user_id == uid))
        db.execute(delete(LoginSession).where(LoginSession.user_id == uid))
        audit(db, user, "staff_verified", "user", uid)
        db.commit()
        return {"verified": True, "role": target.role, "scope": body.scope}

    @app.delete("/api/admin/staff/{uid}", tags=["Auth"])
    def revoke_staff(uid: int, user=Depends(roles("admin")), db=Depends(get_db)):
        revision(db, True)
        grant = db.get(StaffGrant, uid)
        if not grant:
            raise HTTPException(404, "Staff grant not found")
        db.delete(grant)
        db.execute(delete(LoginSession).where(LoginSession.user_id == uid))
        audit(db, user, "staff_revoked", "user", uid)
        db.commit()
        return {"verified": False}

    @app.post("/api/auth/login", tags=["Auth"])
    def login(body: S.Login, db=Depends(get_db)):
        user = db.scalar(select(User).where(User.email == body.email.lower()))
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "Incorrect email or password")
        if user.role in ("company", "placement") and not db.get(StaffGrant, user.id):
            raise HTTPException(
                403, "Staff account requires administrator verification"
            )
        token = secrets.token_urlsafe(40)
        db.add(
            LoginSession(
                token_hash=token_hash(token),
                user_id=user.id,
                expires_at=utcnow() + timedelta(hours=8),
            )
        )
        db.commit()
        return {"access_token": token, "user": user_json(user)}

    @app.get("/api/auth/me", tags=["Auth"])
    def me(user=Depends(current)):
        return user_json(user)

    @app.post("/api/auth/logout", tags=["Auth"])
    def logout(
        credentials: HTTPAuthorizationCredentials = Depends(bearer),
        user=Depends(current),
        db=Depends(get_db),
    ):
        db.delete(db.get(LoginSession, token_hash(credentials.credentials)))
        db.commit()
        return {"ok": True}

    @app.get("/api/skills", tags=["Skills"])
    def skills(
        q: str = "", category: str = "", user=Depends(current), db=Depends(get_db)
    ):
        rows = db.scalars(
            select(Skill).where(Skill.merged_into.is_(None)).order_by(Skill.name)
        ).all()
        query = select(Listing)
        if user.role == "company":
            query = query.where(Listing.owner_id == user.id)
        listings = db.scalars(query).all()
        result = []
        for s in rows:
            if category and category != s.category:
                continue
            if q and q.casefold() not in " ".join([s.name, *s.aliases]).casefold():
                continue
            relevant = [
                listing_json(i)
                for i in listings
                if any(r["skill_id"] == s.id for r in i.details.get("requirements", []))
            ]
            result.append(
                {**skill_json(s), "listing_count": len(relevant), "listings": relevant}
            )
        occupations = [
            {
                "id": o.id,
                "canonical_id": o.canonical_id,
                "name": o.name,
                "source_version": o.source_version,
            }
            for o in db.scalars(select(Occupation).order_by(Occupation.name))
        ]
        return {
            "skills": result,
            "categories": sorted({s.category for s in rows}),
            "occupations": occupations,
            "demand_note": "Counts are from actual imported listings, not ESCO/O*NET employer demand.",
            "date_range": {
                "from": min(
                    [
                        i.details["last_verified"]
                        for i in listings
                        if i.details.get("last_verified")
                    ]
                    or ["unknown"]
                ),
                "to": utcnow().date().isoformat(),
            },
        }

    @app.post("/api/admin/skills", tags=["Skills"])
    def add_skill(body: S.SkillInput, user=Depends(roles("admin")), db=Depends(get_db)):
        revision(db, True)
        if db.scalar(select(Skill).where(Skill.canonical_id == body.canonical_id)):
            raise HTTPException(409, "Canonical ID exists")
        row = Skill(**body.model_dump())
        db.add(row)
        db.commit()
        return skill_json(row)

    @app.put("/api/admin/skills/{sid}", tags=["Skills"])
    def edit_skill(
        sid: int, body: S.SkillInput, user=Depends(roles("admin")), db=Depends(get_db)
    ):
        revision(db, True)
        row = db.get(Skill, sid)
        if not row:
            raise HTTPException(404, "Skill not found")
        for key, value in body.model_dump().items():
            setattr(row, key, value)
        db.commit()
        return skill_json(row)

    @app.post("/api/admin/skills/{sid}/merge/{target}", tags=["Skills"])
    def merge_skill(
        sid: int, target: int, user=Depends(roles("admin")), db=Depends(get_db)
    ):
        revision(db, True)
        source = db.get(Skill, sid)
        dest = db.get(Skill, target)
        if not source or not dest or sid == target or dest.merged_into:
            raise HTTPException(422, "Choose distinct existing canonical skills")
        dest.aliases = sorted(set([*dest.aliases, source.name, *source.aliases]))
        source.merged_into = target
        for e in db.scalars(select(Evidence).where(Evidence.skill_id == sid)):
            e.skill_id = target
            e.value = dest.name
        for listing in db.scalars(select(Listing)):
            data = dict(listing.details)
            data["requirements"] = [
                {**r, "skill_id": target if r["skill_id"] == sid else r["skill_id"]}
                for r in data.get("requirements", [])
            ]
            listing.details = data
        db.commit()
        return {"merged": sid, "into": target}

    @app.post("/api/admin/skills/import", tags=["Skills"])
    def catalog_import(
        payload: dict = Body(...), user=Depends(roles("admin")), db=Depends(get_db)
    ):
        revision(db, True)
        source = payload.get("source")
        version = payload.get("version")
        if source not in ("ESCO", "O*NET", "curated") or not version:
            raise HTTPException(422, "Provide ESCO/O*NET/curated source and version")
        result = import_skills(db, payload.get("rows", []), source, version)
        db.commit()
        return result

    @app.post("/api/admin/occupations/import", tags=["Skills"])
    def occupation_import(
        payload: dict = Body(...), user=Depends(roles("admin")), db=Depends(get_db)
    ):
        revision(db, True)
        added = 0
        if payload.get("source") != "ESCO occupations" or not payload.get(
            "requested_version"
        ):
            raise HTTPException(422, "Retain ESCO occupational source and version")
        for row in payload.get("records", []):
            cid = row.get("conceptUri")
            name = row.get("preferredLabel")
            if not cid or not name:
                raise HTTPException(
                    422, "Occupational URI and preferred label required"
                )
            if not db.scalar(select(Occupation).where(Occupation.canonical_id == cid)):
                db.add(
                    Occupation(
                        canonical_id=cid,
                        name=name,
                        source_version=payload["requested_version"]
                        + "; retrieved "
                        + payload.get("retrieved_at", "unknown"),
                        source_record=row,
                    )
                )
                added += 1
        db.commit()
        return {
            "added": added,
            "notice": "Occupational concepts do not establish Indian internship demand.",
        }

    @app.get("/api/skills/{sid}/versions", tags=["Skills"])
    def skill_versions(sid: int, user=Depends(current), db=Depends(get_db)):
        skill = db.get(Skill, sid)
        if not skill:
            raise HTTPException(404, "Skill not found")
        snapshots = db.scalars(
            select(SkillVersion)
            .where(SkillVersion.skill_id == sid)
            .order_by(SkillVersion.source_version)
        )
        return {
            "current": skill_json(skill),
            "history": [
                {"source_version": v.source_version, **v.details} for v in snapshots
            ],
        }

    @app.get("/api/skills/{sid}/related", tags=["Skills"])
    def semantic_related(sid: int, user=Depends(current), db=Depends(get_db)):
        skill = db.get(Skill, sid)
        if not skill:
            raise HTTPException(404, "Skill not found")
        rows = list(
            db.scalars(
                select(Skill)
                .where(Skill.merged_into.is_(None), Skill.id != sid)
                .limit(10000)
            )
        )
        vectors = embedder.encode([skill.name, *[s.name for s in rows]])
        if vectors is None:
            return {"suggestions": [], "status": embedder.detail, "verified": False}
        import numpy as np

        similarity = np.array(vectors[1:]) @ np.array(vectors[0])
        order = np.argsort(-similarity)[:8]
        return {
            "suggestions": [
                {
                    "skill_id": rows[int(n)].id,
                    "name": rows[int(n)].name,
                    "similarity": float(similarity[n]),
                    "verified": False,
                }
                for n in order
            ],
            "status": "Semantic proposals only; not exact aliases or verified participant skills.",
        }

    @app.get("/api/listings", tags=["Listings"])
    def listings(
        q: str = "",
        location: str = "",
        skill_id: int | None = None,
        source: str = "",
        user=Depends(current),
        db=Depends(get_db),
    ):
        rows = db.scalars(select(Listing).order_by(Listing.id.desc())).all()
        return [
            listing_json(i)
            for i in rows
            if (user.role != "company" or i.owner_id == user.id)
            and (user.role != "applicant" or student_open_listing(i))
            and (
                user.role != "placement"
                or (
                    (grant := db.get(StaffGrant, user.id))
                    and i.details.get("organization", "").casefold()
                    == grant.scope.casefold()
                )
            )
            and (not q or q.casefold() in json.dumps(i.details).casefold())
            and (
                not location
                or location.casefold() in (i.details.get("location") or "").casefold()
            )
            and (not source or source == i.details["source_name"])
            and (
                not skill_id
                or any(
                    r["skill_id"] == skill_id for r in i.details.get("requirements", [])
                )
            )
        ]

    @app.post("/api/import/listings/preview", tags=["Imports"])
    def preview_import(
        records: list[dict] = Body(...),
        user=Depends(roles("admin", "company", "placement")),
        db=Depends(get_db),
    ):
        if len(records) > 1000:
            raise HTTPException(422, "At most 1000 rows per import")
        return listing_preview(db, records)

    @app.post("/api/import/listings/csv-preview", tags=["Imports"])
    async def csv_preview(
        file: UploadFile = File(...),
        user=Depends(roles("admin", "company", "placement")),
        db=Depends(get_db),
    ):
        content = await file.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(413, "CSV too large")
        try:
            rows = parse_listing_csv(content)
        except (UnicodeError, ValueError, csv.Error):
            raise HTTPException(
                422, "The file must be UTF-8 CSV with valid JSON columns"
            ) from None
        if len(rows) > 1000:
            raise HTTPException(422, "At most 1000 rows per import")
        return listing_preview(db, rows)

    @app.post("/api/import/listings/commit", tags=["Imports"], status_code=201)
    def commit_import(
        records: list[dict] = Body(...),
        user=Depends(roles("admin", "company", "placement")),
        db=Depends(get_db),
    ):
        revision(db, True)
        if len(records) > 1000:
            raise HTTPException(422, "At most 1000 rows per import")
        preview = listing_preview(db, records)
        ids, imported = [], 0
        for row in preview["rows"]:
            data = row["record"]
            if row["errors"] and row["errors"] != ["Duplicate source URL"]:
                raise HTTPException(422, preview)
            if user.role != "admin":
                scoped_staff(db, user, data["organization"])
            existing = db.scalar(
                select(Listing).where(Listing.source_url == data["source_url"])
            )
            if not existing and row["errors"] == ["Duplicate source URL"] and lever_identity(data["source_url"]):
                raise HTTPException(409, "This Lever posting is already present under its original URL")
            if existing:
                owned(existing, user)
                prior = {k: existing.details.get(k) for k in data}
                if prior != data:
                    raise HTTPException(
                        409,
                        "Source already imported with different data. Use the versioned edit action.",
                    )
                ids.append(existing.id)
                continue
            listing = Listing(
                owner_id=user.id, source_url=data["source_url"], details={}
            )
            db.add(listing)
            db.flush()
            record_version(db, listing, data)
            ids.append(listing.id)
            imported += 1
        db.commit()
        return {"imported": imported, "ids": ids}

    @app.put("/api/listings/{lid}", tags=["Listings"])
    def edit_listing(
        lid: int,
        body: S.ListingInput,
        user=Depends(roles("admin", "company", "placement")),
        db=Depends(get_db),
    ):
        revision(db, True)
        listing = owned(db.get(Listing, lid), user)
        if is_managed(listing.details):
            raise HTTPException(409, "This listing is refreshed from the employer board")
        data = body.model_dump(mode="json")
        if data["source_url"] != listing.source_url and db.scalar(
            select(Listing).where(Listing.source_url == data["source_url"])
        ):
            raise HTTPException(409, "Duplicate URL")
        # Revalidate required excerpts on edits as well as imports.
        for r in data["requirements"]:
            if (
                not db.get(Skill, r["skill_id"])
                or r["excerpt"]
                not in data["description"] + "\n" + data["requirements_text"]
            ):
                raise HTTPException(422, "Requirement lacks source evidence")
        if not all(
            q.casefold()
            in (data["description"] + " " + data["requirements_text"]).casefold()
            for q in data["mandatory_qualifications"]
        ):
            raise HTTPException(
                422, "Mandatory qualifications must be stated in source text"
            )
        if user.role != "admin":
            scoped_staff(db, user, data["organization"])
        listing.source_url = data["source_url"]
        if {k: listing.details.get(k) for k in data} != data:
            record_version(db, listing, data)
        db.commit()
        return listing_json(listing)

    @app.post("/api/admin/listings/{lid}/approve", tags=["Listings"])
    def approve_listing(
        lid: int,
        body: S.ListingApproval,
        user=Depends(roles("admin")),
        db=Depends(get_db),
    ):
        revision(db, True)
        listing = owned(db.get(Listing, lid), user)
        if is_managed(listing.details):
            raise HTTPException(409, "Only a successful employer verification can update this listing")
        version = listing.details.get("listing_version", 1)
        if body.expected_version != version:
            raise HTTPException(409, "Review the latest listing version")
        details = listing.details | {
            "listing_version": version,
            "source_approved": True,
            "verified_by": user.id,
            "verification_reference": body.verification_reference,
        }
        if listing_status(details) != "open":
            raise HTTPException(
                422,
                "Open verification needs a recent verification date and a live or explicitly rolling deadline",
            )
        listing.details = details
        history = db.get(ListingVersion, (lid, version))
        if history is None:
            db.add(ListingVersion(listing_id=lid, version=version, details=details))
        else:
            history.details = details
        audit(db, user, "listing_approved", "listing", lid)
        db.commit()
        return listing_json(listing)

    @app.get("/api/listings/{lid}/versions", tags=["Listings"])
    def listing_versions(
        lid: int,
        user=Depends(roles("admin", "company", "placement")),
        db=Depends(get_db),
    ):
        owned(db.get(Listing, lid), user)
        rows = db.scalars(
            select(ListingVersion)
            .where(ListingVersion.listing_id == lid)
            .order_by(ListingVersion.version)
        )
        return [{"version": row.version, "details": row.details} for row in rows]

    @app.post("/api/listings/analyze", tags=["Listings"])
    def analyze_listing(
        payload: dict = Body(...),
        user=Depends(roles("admin", "company", "placement")),
        db=Depends(get_db),
    ):
        hits = match_skills(
            str(payload.get("text", ""))[:30000],
            db.scalars(select(Skill).where(Skill.merged_into.is_(None))).all(),
        )
        return {
            "suggestions": [{**h, "classification": "mentioned"} for h in hits],
            "note": "Reviewer must classify required/preferred only when source wording supports it.",
        }

    @app.get("/api/applicant/profile", tags=["Applicant"])
    def profile(user=Depends(roles("applicant")), db=Depends(get_db)):
        row = db.get(Profile, user.id)
        return {
            "profile": row.details if row else S.ProfileInput().model_dump(),
            "evidence": [
                evidence_json(e)
                for e in db.scalars(
                    select(Evidence).where(Evidence.applicant_id == user.id)
                )
            ],
            "documents": [
                {"id": d.id, "filename": d.filename, "pages": len(d.pages)}
                for d in db.scalars(
                    select(Document).where(Document.owner_id == user.id)
                )
            ],
        }

    @app.put("/api/applicant/profile", tags=["Applicant"])
    def save_profile(
        body: S.ProfileInput, user=Depends(roles("applicant")), db=Depends(get_db)
    ):
        revision(db, True)
        row = db.get(Profile, user.id)
        if not row:
            row = Profile(user_id=user.id)
            db.add(row)
        row.details = body.model_dump()
        db.commit()
        return row.details

    @app.post("/api/applicant/evidence", tags=["Applicant"])
    def manual_evidence(
        body: S.ManualEvidence, user=Depends(roles("applicant")), db=Depends(get_db)
    ):
        revision(db, True)
        if body.kind == "skill" and (
            not body.skill_id or not db.get(Skill, body.skill_id)
        ):
            raise HTTPException(422, "Select a canonical skill")
        values = body.model_dump()
        if body.kind == "skill":
            skill = db.get(Skill, body.skill_id)
            if skill.merged_into:
                raise HTTPException(422, "Select an active canonical skill")
            values["value"] = skill.name
        row = Evidence(
            applicant_id=user.id,
            document_id=None,
            **values,
            page=1,
            section="Candidate confirmation",
            source="candidate_confirmation",
            status="self_reported",
        )
        db.add(row)
        db.commit()
        return evidence_json(row)

    @app.post("/api/applicant/documents", tags=["Applicant"])
    async def upload_document(
        file: UploadFile = File(...),
        user=Depends(roles("applicant")),
        db=Depends(get_db),
    ):
        profile = db.get(Profile, user.id)
        if not profile or not profile.details.get("consent"):
            raise HTTPException(409, "Record participant consent before upload")
        content = await file.read(10 * 1024 * 1024 + 1)
        await file.close()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(413, "File must be under 10 MB")
        extension = Path(file.filename or "").suffix.lower()
        try:
            pages = parse_document(content, extension)
        except Exception:
            raise HTTPException(
                422, "Use a readable PDF or DOCX within the document limits"
            ) from None
        if sum(len(page["text"]) for page in pages) > 200_000:
            raise HTTPException(
                413, "Extracted resume text exceeds the permitted limit"
            )
        revision(db, True)
        did = str(uuid.uuid4())
        key = did + extension
        document = Document(
            id=did,
            owner_id=user.id,
            filename=Path(file.filename or "resume").name[:200],
            storage_key=key,
            pages=pages,
        )
        db.add(document)
        db.flush()
        result = extract_document(
            db,
            document,
            provider,
            user.name,
            allow_hosted=profile.details.get(
                "approved_hosted_resume_processing", False
            ),
        )
        stored = uploads / key
        try:
            stored.write_bytes(content)
            db.commit()
        except Exception:
            stored.unlink(missing_ok=True)
            raise
        return {
            "document_id": did,
            **result,
            "notice": (
                "Model provider unavailable. Review the local suggestions."
                if result["provider_unavailable"]
                else "Review each suggestion before adding it to your profile."
            ),
        }

    @app.get("/api/applicant/documents/{did}", tags=["Applicant"])
    def get_document(
        did: str, user=Depends(roles("applicant")), db=Depends(get_db)
    ):
        doc = owned(db.get(Document, did), user)
        if not doc.storage_key:
            raise HTTPException(404, "File removed")
        return FileResponse(uploads / doc.storage_key, filename=doc.filename)

    @app.post("/api/applicant/suggestions/{eid}", tags=["Applicant"])
    def decide_suggestion(
        eid: int,
        body: S.ResumeDecision,
        user=Depends(roles("applicant")),
        db=Depends(get_db),
    ):
        revision(db, True)
        item = owned(db.get(Evidence, eid), user, owner="applicant_id")
        if (
            not item.document_id
            or item.reviewed_by
            or item.status not in ("suggested", "needs_review", "verified")
        ):
            raise HTTPException(409, "This suggestion is no longer pending")
        if body.action == "reject":
            item.status = "rejected"
        elif body.action == "accept":
            skill = db.get(Skill, item.skill_id) if item.skill_id else None
            if not claim_supported(item.kind, item.value, item.excerpt, skill):
                raise HTTPException(422, "Edit the claim as self-reported or reject it")
            item.status = "resume_supported"
        else:
            if not body.value:
                raise HTTPException(422, "Enter the corrected value")
            if item.kind == "skill":
                skill = db.get(Skill, body.skill_id) if body.skill_id else None
                if not skill or skill.merged_into:
                    raise HTTPException(
                        422, "Select an active canonical skill for the edited claim"
                    )
                item.value, item.skill_id = skill.name, skill.id
            else:
                item.value = body.value
            item.document_id = None
            item.excerpt = ""
            item.source = "candidate_confirmation"
            item.status = "self_reported"
        db.commit()
        return evidence_json(item)

    @app.delete("/api/applicant/documents/{did}", tags=["Applicant"])
    def delete_document(did: str, user=Depends(roles("applicant")), db=Depends(get_db)):
        revision(db, True)
        doc = owned(db.get(Document, did), user)
        key = doc.storage_key
        db.execute(delete(Evidence).where(Evidence.document_id == did))
        db.delete(doc)
        db.commit()
        if key:
            (uploads / key).unlink(missing_ok=True)
        return {"deleted": True}

    @app.delete("/api/applicant/data", tags=["Applicant"])
    def delete_data(user=Depends(roles("applicant")), db=Depends(get_db)):
        revision(db, True)
        cases = list(
            db.scalars(select(AgentCase).where(AgentCase.applicant_id == user.id))
        )
        for case in cases:
            app.state.saver.delete_thread(case.id)
            db.execute(delete(Activity).where(Activity.case_id == case.id))
            db.delete(case)
        db.execute(delete(Evidence).where(Evidence.applicant_id == user.id))
        for doc in db.scalars(select(Document).where(Document.owner_id == user.id)):
            if doc.storage_key:
                (uploads / doc.storage_key).unlink(missing_ok=True)
            db.delete(doc)
        db.execute(delete(Choice).where(Choice.applicant_id == user.id))
        db.execute(
            delete(RoundParticipation).where(RoundParticipation.applicant_id == user.id)
        )
        row = db.get(Profile, user.id)
        if row:
            db.delete(row)
        # Remove derived applicant representations from snapshots and revoke affected publication.
        for control in db.scalars(select(RoundControl)):
            if control.snapshot and any(
                a["id"] == user.id for a in control.snapshot.get("applicants", [])
            ):
                control.snapshot = None
                control.snapshot_hash = None
        for draft in db.scalars(select(Draft)):
            snapshot = draft.result.get("input_snapshot", {})
            if any(a["id"] == user.id for a in snapshot.get("applicants", [])):
                app.state.saver.delete_thread("draft-" + str(draft.id))
                db.delete(draft)
        db.commit()
        return {
            "deleted": True,
            "account_retained": True,
            "notice": "Uploaded documents, evidence, choices, agent checkpoints and affected derived drafts removed.",
        }

    @app.get("/api/applicant/recommendations", tags=["Applicant"])
    def recommendations(user=Depends(roles("applicant")), db=Depends(get_db)):
        a = applicant_snapshot(db, user.id)
        rows = [{"id": i.id, **i.details} for i in db.scalars(select(Listing)) if student_open_listing(i)]
        pairs, excluded = pairs_for([a], rows, {}, ranked=False)
        lookup = {i["id"]: i for i in rows}
        # Recommendations may carry unresolved eligibility notes, but never assign a seat.
        for excluded_pair in excluded:
            if excluded_pair["status"] == "needs_review":
                i = lookup[excluded_pair["listing_id"]]
                pairs.append(
                    {
                        "applicant_id": user.id,
                        "listing_id": i["id"],
                        "rank": None,
                        **score(a, i, {}),
                        "eligibility_status": "needs_review",
                        "decision": "REVIEW",
                        "eligibility_reasons": excluded_pair["reasons"],
                    }
                )
        pairs = [p for p in pairs if (isolated_fixtures and not is_managed(lookup[p["listing_id"]]))
                 or relevant_match(p)]
        return {
            "mode": "recommendation",
            "seat_assigned": False,
            "message": None if pairs else NO_MATCHES,
            "recommendations": [
                {**p, "listing": {**lookup[p["listing_id"]], "status": "open"}}
                for p in sorted(
                    pairs,
                    key=lambda p: (
                        not p["coverage_threshold_met"],
                        p["score"] is None,
                        -(p["score"] or 0),
                        -p["evidence_coverage"],
                        p["listing_id"],
                    ),
                )
            ],
            "eligibility_notes": excluded,
            "missing_inputs": (
                [] if a.get("skills") else ["No accepted skills in the profile"]
            )
            + ([] if rows else ["No real listings imported"]),
        }

    @app.post("/api/applicant/matches/{lid}/explanation", tags=["Applicant"])
    def explain_match(lid: int, user=Depends(roles("applicant")), db=Depends(get_db)):
        listing = db.get(Listing, lid)
        if not listing:
            raise HTTPException(404, "Listing not found")
        a = applicant_snapshot(db, user.id)
        if not student_open_listing(listing):
            raise HTTPException(
                409, "A verified open listing is required for a match explanation"
            )
        match = score(a, {"id": lid, **listing.details}, {})
        from .engine import eligible

        eligibility = eligible(a, {"id": lid, **listing.details}, {})
        names = lambda ids: (
            ", ".join(db.get(Skill, sid).name for sid in ids if db.get(Skill, sid))
            or "none"
        )
        facts = {
            "mode": "This is a recommendation only; no seat has been assigned.",
            "score": (
                f"Fit is {match['score']:.1f} out of 100."
                if match["score"] is not None
                else "Fit is unknown."
            )
            + f" Evidence coverage is {match['evidence_coverage']:.0%}.",
            "matched": "Accepted exact skill matches: "
            + names(match["matched_skills"])
            + ".",
            "missing": "Skills absent from the profile: "
            + names(match["missing_skills"])
            + ".",
            "eligibility": "Eligibility status: "
            + eligibility["status"]
            + ". "
            + (
                "; ".join(eligibility["reasons"])
                or "Configured checks passed; this is not an official eligibility certification."
            ),
        }
        if provider.mode == "live" and a.get("approved_hosted_resume_processing"):
            try:
                if provider.qualify():
                    return provider.explain(facts)
            except Exception:
                pass
        return {
            "text": " ".join(facts.values()),
            "fact_ids": list(facts),
            "mode": "fixture",
            "method": "Deterministic explanation from the applicant's match evidence",
        }

    @app.get("/api/policies", tags=["Policy"])
    def policies(user=Depends(current), db=Depends(get_db)):
        return [
            {
                "id": p.id,
                "name": p.name,
                "config": p.config,
                "document_ids": p.document_ids,
                "approved_by": p.approved_by,
            }
            for p in db.scalars(select(Policy).order_by(Policy.id.desc()))
        ]

    @app.get("/api/admin/policy-documents", tags=["Policy"])
    def policy_documents(user=Depends(roles("admin")), db=Depends(get_db)):
        return [
            {
                "id": d.id,
                "title": d.title,
                "scope": d.scope,
                "version": d.version,
                "effective_date": d.effective_date,
                "source_url": d.source_url,
                "passages": [
                    {
                        "id": p.id,
                        "section": p.section,
                        "content": p.content,
                        "indexed": p.embedding is not None,
                    }
                    for p in db.scalars(
                        select(Passage).where(Passage.document_id == d.id)
                    )
                ],
            }
            for d in db.scalars(select(PolicyDocument))
        ]

    @app.post("/api/admin/policy-documents", tags=["Policy"])
    def import_policy(
        body: S.PolicyDocumentInput, user=Depends(roles("admin")), db=Depends(get_db)
    ):
        revision(db, True)
        raw = body.model_dump(mode="json")
        if body.effective_until and body.effective_until < body.effective_date:
            raise HTTPException(422, "Effective end precedes effective start")
        if sum(len(c) for c in body.sections.values()) > 400000:
            raise HTTPException(413, "Policy text is too long")
        extra = {"publisher", "scheme", "published_on", "effective_until"}
        doc = PolicyDocument(
            **{k: v for k, v in raw.items() if k not in extra | {"sections"}}
        )
        db.add(doc)
        db.flush()
        db.add(
            PolicyProvenance(
                document_id=doc.id,
                details={
                    **{k: raw[k] for k in extra},
                    "hash": fingerprint(raw),
                    "approved": False,
                },
            )
        )
        sections = [
            (section, content[n : n + 1400])
            for section, content in body.sections.items()
            for n in range(0, len(content), 1200)
        ]
        vectors = embedder.encode([c for _, c in sections])
        for n, (section, content) in enumerate(sections):
            db.add(
                Passage(
                    document_id=doc.id,
                    section=section,
                    content=content,
                    embedding=vectors[n] if vectors else None,
                    embedding_model=MODEL if vectors else None,
                )
            )
        db.commit()
        return {
            "id": doc.id,
            "passages": len(sections),
            "vector_indexed": vectors is not None,
            "embedding_status": embedder.detail,
        }

    @app.post("/api/admin/policy-documents/reindex", tags=["Policy"])
    def reindex(user=Depends(roles("admin")), db=Depends(get_db)):
        rows = db.scalars(select(Passage)).all()
        vectors = embedder.encode([p.content for p in rows]) if rows else []
        if vectors is None:
            raise HTTPException(409, embedder.detail)
        for p, v in zip(rows, vectors):
            p.embedding = v
            p.embedding_model = MODEL
        db.commit()
        return {"indexed": len(rows)}

    @app.post("/api/admin/policies", tags=["Policy"])
    def create_policy(
        body: S.PolicyInput, user=Depends(roles("admin")), db=Depends(get_db)
    ):
        revision(db, True)
        if any(not db.get(PolicyDocument, i) for i in body.document_ids):
            raise HTTPException(422, "Unknown policy document")
        if (
            body.config.minimum_placements
            or body.config.equity_weight
            or body.config.equity_adjustments
        ):
            raise HTTPException(
                422,
                "Additional group constraints are outside the approved research objective",
            )
        if body.config.coverage_confirmed and (
            not body.config.scheme or not body.config.effective_date
        ):
            raise HTTPException(
                422, "Coverage confirmation requires a scheme and effective date"
            )
        if (body.config.require_noc or body.config.exclude_prior_participants) and not body.document_ids:
            raise HTTPException(
                422, "Attach the applicable approved source for an evidence requirement"
            )
        row = Policy(
            name=body.name,
            config=body.config.model_dump(mode="json"),
            document_ids=body.document_ids,
        )
        db.add(row)
        db.commit()
        return {"id": row.id, "approved_by": None}

    @app.post("/api/admin/policies/{pid}/approve", tags=["Policy"])
    def approve_policy(pid: int, user=Depends(roles("admin")), db=Depends(get_db)):
        revision(db, True)
        row = db.get(Policy, pid)
        if not row:
            raise HTTPException(404, "Policy not found")
        if not row.approved_by:
            row.approved_by = user.id
        for did in row.document_ids:
            provenance = db.get(PolicyProvenance, did)
            if provenance:
                if (
                    row.config.get("scheme")
                    and provenance.details.get("scheme") != row.config["scheme"]
                ):
                    raise HTTPException(
                        422, "Document scheme differs from policy scope"
                    )
                provenance.details = provenance.details | {
                    "approved": True,
                    "approved_by": user.id,
                }
        db.commit()
        return {
            "id": pid,
            "approved_by": user.id,
            "notice": "Only this configuration controls solver constraints; retrieved text does not.",
        }

    @app.post("/api/policy/search", tags=["Policy"])
    def search_policy(
        body: S.RetrievalQuestion, user=Depends(current), db=Depends(get_db)
    ):
        policy = db.get(Policy, body.policy_id)
        if not policy or not policy.approved_by:
            raise HTTPException(404, "Approved policy version not found")
        return answer(db, body.question, policy, embedder, body.mode)

    @app.post("/api/mcp/policy/search", tags=["Policy"])
    def mcp_search(
        body: S.RetrievalQuestion,
        credentials: HTTPAuthorizationCredentials = Depends(bearer),
        db=Depends(get_db),
    ):
        token = os.getenv("MCP_POLICY_TOKEN", "")
        if (
            len(token) < 32
            or not credentials
            or not secrets.compare_digest(
                token_hash(credentials.credentials), token_hash(token)
            )
        ):
            raise HTTPException(401, "Valid policy-only token required")
        allowed = {
            int(i)
            for i in os.getenv("MCP_POLICY_IDS", "").split(",")
            if i.strip().isdigit()
        }
        policy = db.get(Policy, body.policy_id) if body.policy_id in allowed else None
        if not policy or not policy.approved_by:
            raise HTTPException(404, "Approved policy is outside the MCP scope")
        if engine.dialect.name == "postgresql":
            with engine.connect() as connection:
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                from sqlalchemy.orm import Session as ReadSession

                with ReadSession(bind=connection) as scoped:
                    return answer(
                        scoped,
                        body.question,
                        scoped.get(Policy, policy.id),
                        embedder,
                        body.mode,
                    )
        return answer(db, body.question, policy, embedder, body.mode)

    @app.post("/api/admin/evaluate/retrieval", tags=["Evaluation"])
    def eval_retrieval(
        labels: list[dict] = Body(...), user=Depends(roles("admin")), db=Depends(get_db)
    ):
        if not labels or len(labels) > 200:
            raise HTTPException(422, "Supply 1–200 labeled questions")
        return evaluate(db, labels, embedder)

    @app.post("/api/admin/evaluate/extraction", tags=["Evaluation"])
    def eval_extraction(
        payload: dict = Body(...), user=Depends(roles("admin")), db=Depends(get_db)
    ):
        if (
            payload.get("authorized") is not True
            or payload.get("deidentified") is not True
        ):
            raise HTTPException(
                422, "Authorized, de-identified evaluation input is required"
            )
        records = payload.get("records", [])
        if not 1 <= len(records) <= 100 or any(
            len(str(r.get("text", ""))) > 30000 for r in records
        ):
            raise HTTPException(422, "Supply 1–100 bounded evaluation records")
        if any("text" not in r or "gold_skill_ids" not in r for r in records):
            raise HTTPException(422, "Each record requires text and gold_skill_ids")
        return extraction_evaluation(
            records,
            list(db.scalars(select(Skill).where(Skill.merged_into.is_(None)))),
            provider,
        )

    @app.get("/api/rounds", tags=["Allocation"])
    def rounds(user=Depends(current), db=Depends(get_db)):
        return [
            {
                "id": r.id,
                "name": r.name,
                "policy_id": r.policy_id,
                "listing_ids": control.listing_ids if control else [],
                "scope": control.scope if control else None,
                "frozen": bool(control and control.snapshot),
                "capacities": [
                    {
                        "listing_id": c.listing_id,
                        "seats": c.seats,
                        **(
                            {
                                "confirmed_by": c.confirmed_by,
                                "confirmation_reference": c.confirmation_reference,
                            }
                            if user.role == "admin"
                            or (user.role == "company" and c.confirmed_by == user.id)
                            else {}
                        ),
                    }
                    for c in db.scalars(
                        select(Capacity).where(Capacity.round_id == r.id)
                    )
                    if user.role != "company"
                    or db.get(Listing, c.listing_id).owner_id == user.id
                ],
                "choices": db.get(Choice, (r.id, user.id)).listing_ids
                if user.role == "applicant" and db.get(Choice, (r.id, user.id))
                else [],
                **({"choice_listings": [
                    {"id": item.id, "title": item.details["title"], "status": listing_status(item.details)}
                    for item in db.scalars(select(Listing).where(Listing.id.in_(control.listing_ids)))
                ]} if user.role == "applicant" and control else {}),
            }
            for r in db.scalars(select(Round))
            for control in [db.get(RoundControl, r.id)]
            if (
                user.role not in ("company", "placement")
                or (
                    control
                    and (grant := db.get(StaffGrant, user.id))
                    and grant.scope.casefold() == control.scope.casefold()
                )
            )
            and (
                user.role != "applicant" or db.get(RoundParticipation, (r.id, user.id))
            )
        ]

    @app.post("/api/admin/rounds", tags=["Allocation"])
    def create_round(
        body: S.RoundInput,
        user=Depends(roles("admin", "placement")),
        db=Depends(get_db),
    ):
        revision(db, True)
        if user.role == "placement":
            scoped_staff(db, user, body.scope)
        policy = db.get(Policy, body.policy_id)
        if not policy or not policy.approved_by:
            raise HTTPException(409, "Approve the policy configuration first")
        if (
            not policy.config.get("coverage_confirmed")
            or (policy.config.get("effective_date") or "9999")
            > date.today().isoformat()
        ):
            raise HTTPException(
                409, "Confirm current applicable rule coverage before creating a round"
            )
        ids = sorted(set(body.listing_ids))
        for lid in ids:
            listing = db.get(Listing, lid)
            if not listing or listing_status(listing.details) != "open":
                raise HTTPException(422, "Every role must have a verified open listing")
            grant = db.get(StaffGrant, listing.owner_id)
            owner = db.get(User, listing.owner_id)
            if (owner.role != "admin" or user.role == "placement") and (
                not grant or grant.scope.casefold() != body.scope.casefold()
            ):
                raise HTTPException(
                    403, "The listing owner is outside the round's verified scope"
                )
        row = Round(name=body.name, policy_id=body.policy_id)
        db.add(row)
        db.flush()
        db.add(
            RoundControl(
                round_id=row.id,
                scope=body.scope,
                listing_ids=ids,
                tie_seed=secrets.token_hex(32),
            )
        )
        audit(db, user, "round_created", "round", row.id)
        db.commit()
        return {"id": row.id, "name": row.name, "listing_ids": ids}

    @app.put("/api/admin/rounds/{rid}/participation", tags=["Allocation"])
    def authorize_participation(
        rid: int,
        body: S.ParticipationInput,
        user=Depends(roles("admin", "placement")),
        db=Depends(get_db),
    ):
        revision(db, True)
        control = controlled_round(db, rid, collecting=True)
        if user.role == "placement":
            scoped_staff(db, user, control.scope)
        member = db.get(User, body.applicant_id)
        if not member or member.role != "applicant":
            raise HTTPException(422, "Choose an authorized applicant account")
        db.merge(
            RoundParticipation(
                round_id=rid,
                **body.model_dump(),
                authorized_by=user.id,
                authorized_at=utcnow(),
            )
        )
        audit(db, user, "participation_authorized", "round", rid)
        db.commit()
        return {"authorized": True}

    @app.delete("/api/admin/rounds/{rid}/participation/{uid}", tags=["Allocation"])
    def revoke_participation(
        rid: int,
        uid: int,
        user=Depends(roles("admin", "placement")),
        db=Depends(get_db),
    ):
        revision(db, True)
        control = controlled_round(db, rid)
        if user.role == "placement":
            scoped_staff(db, user, control.scope)
        member = db.get(RoundParticipation, (rid, uid))
        if not member:
            raise HTTPException(404, "Participation not found")
        db.delete(member)
        # Any old snapshot still includes the prior grant and cannot be reused.
        db.execute(
            delete(Choice).where(Choice.round_id == rid, Choice.applicant_id == uid)
        )
        audit(db, user, "participation_revoked", "round", rid)
        db.commit()
        return {"authorized": False}

    @app.get("/api/admin/rounds/{rid}/participation", tags=["Allocation"])
    def list_participation(
        rid: int, user=Depends(roles("admin", "placement")), db=Depends(get_db)
    ):
        control = controlled_round(db, rid)
        if user.role == "placement":
            scoped_staff(db, user, control.scope)
        members = db.scalars(
            select(RoundParticipation).where(RoundParticipation.round_id == rid)
        )
        return [
            {
                "applicant_id": row.applicant_id,
                "choices_submitted": bool(db.get(Choice, (rid, row.applicant_id))),
            }
            for row in members
        ]

    @app.put("/api/rounds/{rid}/capacity", tags=["Allocation"])
    def confirm_capacity(
        rid: int,
        body: S.CapacityInput,
        user=Depends(roles("company", "placement")),
        db=Depends(get_db),
    ):
        revision(db, True)
        control = controlled_round(db, rid, collecting=True)
        listing = db.get(Listing, body.listing_id)
        if (
            not listing
            or body.listing_id not in control.listing_ids
            or listing_status(listing.details) != "open"
        ):
            raise HTTPException(
                409, "Only verified open roles in the round may receive seats"
            )
        scoped_staff(db, user, control.scope)
        if user.role != "placement":
            if listing.owner_id != user.id:
                raise HTTPException(
                    403, "The listing owner or scoped placement staff must attest"
                )
        cap = db.get(Capacity, (rid, body.listing_id))
        if not cap:
            cap = Capacity(round_id=rid, listing_id=body.listing_id)
            db.add(cap)
        cap.seats = body.seats
        cap.confirmed_by = user.id
        cap.confirmation_reference = body.confirmation_reference
        number = (
            db.scalar(
                select(func.max(SeatEvidence.version)).where(
                    SeatEvidence.round_id == rid,
                    SeatEvidence.listing_id == body.listing_id,
                )
            )
            or 0
        )
        db.add(
            SeatEvidence(
                round_id=rid,
                listing_id=body.listing_id,
                version=number + 1,
                payload={
                    "scope": control.scope,
                    "seats": cap.seats,
                    "confirmed_by": user.id,
                    "reference": body.confirmation_reference,
                    "revoked": False,
                    "listing_version": listing.details.get("listing_version", 1),
                },
            )
        )
        db.commit()
        return {"confirmed": True, "seats": cap.seats, "version": number + 1}

    @app.post("/api/admin/rounds/{rid}/capacity/{lid}/revoke", tags=["Allocation"])
    def revoke_capacity(
        rid: int, lid: int, user=Depends(roles("admin")), db=Depends(get_db)
    ):
        revision(db, True)
        number = db.scalar(
            select(func.max(SeatEvidence.version)).where(
                SeatEvidence.round_id == rid, SeatEvidence.listing_id == lid
            )
        )
        if not number:
            raise HTTPException(404, "No attestation found")
        prior = db.get(SeatEvidence, (rid, lid, number))
        db.add(
            SeatEvidence(
                round_id=rid,
                listing_id=lid,
                version=number + 1,
                payload=prior.payload | {"revoked": True, "revoked_by": user.id},
            )
        )
        db.commit()
        return {"revoked": True}

    @app.post("/api/admin/rounds/{rid}/freeze", tags=["Allocation"])
    def freeze_round(
        rid: int, user=Depends(roles("admin", "placement")), db=Depends(get_db)
    ):
        revision(db, True)
        control = controlled_round(db, rid, collecting=True)
        if user.role == "placement":
            scoped_staff(db, user, control.scope)
        applicants, listings, policy = round_snapshot(db, rid)
        frozen = {
            "applicants": applicants,
            "listings": listings,
            "rules": policy.config
            | {"policy_version": policy.id, "tie_seed": control.tie_seed},
        }
        control.snapshot = frozen
        control.snapshot_hash = fingerprint(frozen)
        audit(db, user, "round_frozen", "round", rid)
        db.commit()
        return {"round_id": rid, "frozen": True, "snapshot_hash": control.snapshot_hash}

    @app.post("/api/admin/rounds/{rid}/reopen", tags=["Allocation"])
    def reopen_round(rid: int, user=Depends(roles("admin")), db=Depends(get_db)):
        revision(db, True)
        control = controlled_round(db, rid)
        if db.scalar(
            select(Draft.id)
            .where(Draft.round_id == rid, Draft.published_at.is_not(None))
            .limit(1)
        ):
            raise HTTPException(409, "A published round must remain closed")
        control.snapshot = None
        control.snapshot_hash = None
        db.commit()
        return {"round_id": rid, "frozen": False}

    @app.put("/api/rounds/{rid}/choices", tags=["Allocation"])
    def choices(
        rid: int, body: S.Choices, user=Depends(roles("applicant")), db=Depends(get_db)
    ):
        revision(db, True)
        control = controlled_round(db, rid, collecting=True)
        if not db.get(RoundParticipation, (rid, user.id)):
            raise HTTPException(
                404, "Round is outside your authorized participation scope"
            )
        profile = db.get(Profile, user.id)
        if not profile or not profile.details.get("consent"):
            raise HTTPException(409, "Consent is required to submit choices")
        if not set(body.listing_ids) <= set(control.listing_ids):
            raise HTTPException(422, "Rank only roles in the authorized round scope")
        row = db.get(Choice, (rid, user.id))
        if not row:
            row = Choice(round_id=rid, applicant_id=user.id)
            db.add(row)
        row.listing_ids = body.listing_ids
        db.commit()
        return {"choices": row.listing_ids}

    @app.post("/api/agent/cases", tags=["Agent"])
    def start_case(
        body: S.CaseInput, user=Depends(roles("applicant")), db=Depends(get_db)
    ):
        rid = body.round_id
        policy_id = body.policy_id
        if rid:
            round_ = db.get(Round, rid)
            if not round_ or not db.get(RoundParticipation, (rid, user.id)):
                raise HTTPException(
                    404, "Round is outside your authorized participation scope"
                )
            policy_id = round_.policy_id
        selected = db.get(Policy, policy_id) if policy_id else None
        if policy_id and (not selected or not selected.approved_by):
            raise HTTPException(404, "Policy not found")
        case = AgentCase(
            id=str(uuid.uuid4()),
            applicant_id=user.id,
            round_id=rid,
            policy_id=policy_id,
            revision=revision(db),
            mode=provider.mode,
        )
        db.add(case)
        db.commit()
        with thread_lock(case.id):
            app.state.graph.invoke(
                {
                    "case_id": case.id,
                    "question_available": bool(body.policy_question),
                    "task": "triage",
                    "done": [],
                    "steps": 0,
                },
                graph_config(case.id),
                context={"policy_question": body.policy_question},
            )
        db.refresh(case)
        return case_json(case, db)

    @app.get("/api/agent/cases", tags=["Agent"])
    def cases(user=Depends(roles("applicant", "admin")), db=Depends(get_db)):
        query = select(AgentCase).order_by(AgentCase.id)
        if user.role != "admin":
            query = query.where(AgentCase.applicant_id == user.id)
        return [case_json(c, db) for c in db.scalars(query)]

    @app.get("/api/agent/cases/{cid}", tags=["Agent"])
    def get_case(
        cid: str, user=Depends(roles("applicant", "admin")), db=Depends(get_db)
    ):
        case = owned(db.get(AgentCase, cid), user, "applicant_id")
        return case_json(case, db)

    @app.post("/api/admin/evidence/{eid}/review", tags=["Review"])
    def review_evidence(
        eid: int,
        body: S.EvidenceReview,
        user=Depends(roles("admin")),
        db=Depends(get_db),
    ):
        revision(db, True)
        e = db.get(Evidence, eid)
        if not e:
            raise HTTPException(404, "Evidence not found")
        if (
            body.status == "verified"
            and e.document_id
            and e.status not in ("resume_supported", "verified")
        ):
            raise HTTPException(409, "The applicant must accept resume evidence first")
        if body.status == "verified" and not claim_supported(
            e.kind,
            e.value,
            e.excerpt,
            db.get(Skill, e.skill_id) if e.skill_id else None,
        ):
            raise HTTPException(
                422,
                "Excerpt does not support this claim. Request corrected evidence; do not infer a qualification from a team mention.",
            )
        if body.status == "not_held" and (
            e.kind != "qualification" or not body.note or len(body.note) < 5
        ):
            raise HTTPException(
                422,
                "A qualification-specific confirmed-not-held decision requires an authorized review note",
            )
        if (
            body.status == "verified"
            and not body.note
            and e.kind == "qualification"
            and e.value.strip().casefold() == "noc"
        ):
            raise HTTPException(
                422, "Document the reviewer evidence reference for the NOC"
            )
        e.status = body.status
        e.reviewed_by = user.id
        e.review_note = body.note
        db.commit()
        return evidence_json(e)

    @app.post("/api/admin/agent/cases/{cid}/resume", tags=["Agent"])
    def resume_case(cid: str, user=Depends(roles("admin")), db=Depends(get_db)):
        case = db.get(AgentCase, cid)
        if not case:
            raise HTTPException(404, "Case not found")
        if unresolved_case(db, case):
            raise HTTPException(409, "Required evidence still needs review")
        with thread_lock(cid):
            state = app.state.graph.get_state(graph_config(cid))
            if state.next:
                app.state.graph.invoke(
                    Command(resume={"authorized_review": True}), graph_config(cid)
                )
        db.refresh(case)
        return case_json(case, db)

    @app.post("/api/admin/rounds/{rid}/allocate", tags=["Allocation"])
    def allocate(rid: int, user=Depends(roles("admin")), db=Depends(get_db)):
        current_revision = db.get(State, 1, with_for_update=True).revision
        control = controlled_round(db, rid)
        applicants, listings, policy = round_snapshot(db, rid)
        rules = policy.config | {
            "policy_version": policy.id,
            "tie_seed": control.tie_seed,
        }
        latest = {"applicants": applicants, "listings": listings, "rules": rules}
        if not control.snapshot_hash or control.snapshot_hash != fingerprint(latest):
            raise HTTPException(
                409, "Freeze a current authorized snapshot before solving"
            )
        result = optimize(**control.snapshot)
        result["input_hash"] = control.snapshot_hash
        result["output_hash"] = fingerprint(result["placements"])
        result["policy_version"] = policy.id
        draft = Draft(
            round_id=rid,
            policy_id=policy.id,
            revision=current_revision,
            result=result,
            digest=fingerprint(result),
        )
        db.add(draft)
        db.commit()
        app.state.graph.invoke(
            {"task": "draft_review", "draft_id": draft.id},
            graph_config("draft-" + str(draft.id)),
        )
        return draft_json(draft, db)

    @app.get("/api/admin/drafts", tags=["Allocation"])
    def drafts(user=Depends(roles("admin")), db=Depends(get_db)):
        return [
            draft_json(d, db)
            for d in db.scalars(select(Draft).order_by(Draft.id.desc()))
        ]

    @app.post("/api/admin/drafts/{did}/approve", tags=["Review"])
    def approve_draft(
        did: int, body: S.Acknowledge, user=Depends(roles("admin")), db=Depends(get_db)
    ):
        state = db.get(State, 1, with_for_update=True)
        draft = db.get(Draft, did)
        check_draft(draft, db)
        if body.digest != draft.digest:
            raise HTTPException(409, "Approval must name the exact draft digest")
        if draft.approved_by and draft.approval_digest == draft.digest:
            return draft_json(draft, db)
        output = app.state.graph.invoke(
            Command(resume={"authorized_review": True, "digest": body.digest}),
            graph_config("draft-" + str(did)),
        )
        if not output.get("review_ack"):
            raise HTTPException(409, "Graph review acknowledgement missing")
        draft.approved_by = user.id
        draft.approval_digest = body.digest
        audit(db, user, "draft_approved", "draft", did)
        db.commit()
        return draft_json(draft, db)

    @app.post("/api/admin/drafts/{did}/publish", tags=["Publication"])
    def publish(did: int, user=Depends(roles("admin")), db=Depends(get_db)):
        db.get(State, 1, with_for_update=True)
        draft = db.get(Draft, did)
        if draft and draft.published_at:
            return draft_json(draft, db)
        check_draft(draft, db)
        if not draft.approved_by or draft.approval_digest != draft.digest:
            raise HTTPException(
                409, "Explicit administrator approval of this exact draft is required"
            )
        prior = db.scalar(
            select(Draft.id)
            .where(
                Draft.round_id == draft.round_id,
                Draft.published_at.is_not(None),
                Draft.id != did,
            )
            .limit(1)
        )
        if prior:
            raise HTTPException(
                409, "A different draft has already been published for this round"
            )
        draft.published_at = draft.published_at or utcnow()
        audit(db, user, "draft_published", "draft", did)
        db.commit()
        return draft_json(draft, db)

    @app.get("/api/outcomes", tags=["Publication"])
    def outcomes(user=Depends(current), db=Depends(get_db)):
        published = list(
            db.scalars(
                select(Draft)
                .where(Draft.published_at.is_not(None))
                .order_by(Draft.id.desc())
            )
        )
        seen = set()
        result = []
        for draft in published:
            if draft.round_id in seen:
                continue
            seen.add(draft.round_id)
            snapshot = draft.result["input_snapshot"]
            listing_map = {i["id"]: i for i in snapshot["listings"]}
            for p in draft.result["placements"]:
                listing = listing_map[p["listing_id"]]
                row = db.get(Listing, p["listing_id"])
                if user.role == "applicant" and p["applicant_id"] != user.id:
                    continue
                if user.role == "company" and (not row or row.owner_id != user.id):
                    continue
                if user.role == "placement":
                    scope = db.get(RoundControl, draft.round_id)
                    grant = db.get(StaffGrant, user.id)
                    if (
                        not scope
                        or not grant
                        or scope.scope.casefold() != grant.scope.casefold()
                    ):
                        continue
                result.append(
                    {
                        "draft_id": draft.id,
                        "round_id": draft.round_id,
                        "policy_version": draft.policy_id,
                        "solver_status": draft.result["solver_status"],
                        "outcome": "placed",
                        "listing": {
                            k: listing.get(k)
                            for k in (
                                "id",
                                "title",
                                "organization",
                                "source_url",
                                "location",
                                "work_mode",
                            )
                        },
                        **p,
                        "explanation": f"Verified mandatory evidence, ranked choice #{p['rank']}, available confirmed seat, and approved policy v{draft.policy_id}. This is an internal allocation, not an official offer.",
                    }
                )
            if user.role in ("admin", "applicant"):
                for u in draft.result["unassigned"]:
                    if user.role == "admin" or u["applicant_id"] == user.id:
                        result.append(
                            {
                                "draft_id": draft.id,
                                "round_id": draft.round_id,
                                "policy_version": draft.policy_id,
                                "solver_status": draft.result["solver_status"],
                                "outcome": "unassigned",
                                **u,
                            }
                        )
        return result

    @app.get("/api/admin/drafts/{did}/export", tags=["Publication"])
    def export(did: int, user=Depends(roles("admin")), db=Depends(get_db)):
        draft = db.get(Draft, did)
        if not draft:
            raise HTTPException(404, "Draft not found")
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(
            [
                "draft",
                "policy_version",
                "solver_status",
                "participant_id",
                "listing_id",
                "choice",
                "rank_utility",
                "outcome",
            ]
        )
        for p in draft.result["placements"]:
            writer.writerow(
                [
                    did,
                    draft.policy_id,
                    draft.result["solver_status"],
                    p["applicant_id"],
                    p["listing_id"],
                    p["rank"],
                    p.get("utility"),
                    "placed",
                ]
            )
        for u in draft.result["unassigned"]:
            writer.writerow(
                [
                    did,
                    draft.policy_id,
                    draft.result["solver_status"],
                    u["applicant_id"],
                    "",
                    "",
                    "",
                    u["reason"],
                ]
            )
        return Response(
            stream.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="allocation-{did}.csv"'
            },
        )

    @app.get("/api/admin/evidence", tags=["Review"])
    def evidence_queue(user=Depends(roles("admin")), db=Depends(get_db)):
        return [
            evidence_json(e)
            for e in db.scalars(select(Evidence).order_by(Evidence.id.desc()))
        ]

    @app.post("/api/admin/participants/import", tags=["Imports"])
    def participant_import(
        body: S.ParticipantImport, user=Depends(roles("admin")), db=Depends(get_db)
    ):
        revision(db, True)
        imported = []
        activation_tokens = []
        for record in body.profiles:
            email = record.email.lower().strip()
            if "@" not in email or not record.profile.consent:
                raise HTTPException(
                    422, "Each participant needs a valid email and recorded consent"
                )
            if db.scalar(select(User).where(User.email == email)):
                raise HTTPException(
                    409,
                    "Participant already registered; owner must update existing records",
                )
            person = User(
                name=record.name,
                email=email,
                role="applicant",
                password_hash=hash_password(secrets.token_urlsafe(32)),
            )
            db.add(person)
            db.flush()
            token = secrets.token_urlsafe(32)
            db.add(
                Invitation(
                    token_hash=token_hash(token),
                    user_id=person.id,
                    expires_at=utcnow() + timedelta(hours=48),
                )
            )
            activation_tokens.append({"email": email, "activation_token": token})
            db.add(Profile(user_id=person.id, details=record.profile.model_dump()))
            for claim in record.evidence:
                if claim.kind == "skill" and not db.get(Skill, claim.skill_id):
                    raise HTTPException(422, "Unknown canonical skill")
                db.add(
                    Evidence(
                        applicant_id=person.id,
                        document_id=None,
                        **claim.model_dump(),
                        page=1,
                        section="Authorized placement-cell import",
                        source="candidate_confirmation",
                        status="needs_review",
                    )
                )
            imported.append(person.id)
        db.commit()
        return {
            "participant_ids": imported,
            "activation_tokens": activation_tokens,
            "notice": "Imported records require evidence review. Give each participant their own one-time token through an authorized channel. They register as Applicant with the same email and token to set their password. Tokens expire after 48 hours.",
        }

    @app.get("/api/admin/audit", tags=["System"])
    def audit_history(user=Depends(roles("admin")), db=Depends(get_db)):
        return [
            {
                "id": event.id,
                "action": event.action,
                "actor_id": event.actor_id,
                "entity": event.entity,
                "entity_id": event.entity_id,
                "at": event.at.isoformat(),
            }
            for event in db.scalars(
                select(AuditEvent).order_by(AuditEvent.id.desc()).limit(100)
            )
        ]

    @app.get("/api/dashboard", tags=["System"])
    def dashboard(user=Depends(current), db=Depends(get_db)):
        counts = {
            name: db.scalar(select(func.count()).select_from(model))
            for name, model in [
                ("listings", Listing),
                ("participants", Profile),
                ("skills", Skill),
                ("policy_documents", PolicyDocument),
                ("rounds", Round),
                ("confirmed_capacities", Capacity),
            ]
        }
        return {
            "counts": counts,
            "database": engine.dialect.name,
            "llm_mode": provider.mode,
            "fixture_notice": "Deterministic fixture tool selection and template extraction on imported real records; not a live LLM evaluation."
            if provider.mode == "fixture"
            else "Live structured extraction and tool calling",
            "embedding_status": embedder.detail,
            "missing_inputs": [
                message
                for field, message in [
                    ("listings", "Import real verified internship listings"),
                    ("policy_documents", "Import dated policy documents"),
                    ("participants", "Participants must register and consent"),
                    (
                        "confirmed_capacities",
                        "Employer-confirmed capacities required for allocation",
                    ),
                ]
                if not counts[field]
            ],
            "revision": revision(db),
            "responsibilities": [
                "LLM extracts and explains",
                "Agent selects evidence tools",
                "Optimizer assigns confirmed seats",
                "Administrator approves publication",
            ],
        }

    return app
