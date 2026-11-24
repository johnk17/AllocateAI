"""PostgreSQL schema; SQLite is only used in isolated unit tests."""

import os
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine,
    String,
    Integer,
    JSON,
    ForeignKey,
    DateTime,
    Text,
    Boolean,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from pgvector.sqlalchemy import Vector


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "ai_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(Text)


class StaffGrant(Base):
    __tablename__ = "ai_staff_grants"
    user_id: Mapped[int] = mapped_column(ForeignKey("ai_users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    scope: Mapped[str] = mapped_column(String(200))
    evidence_reference: Mapped[str] = mapped_column(String(500))
    approved_by: Mapped[int] = mapped_column(ForeignKey("ai_users.id"))
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class StaffRequest(Base):
    __tablename__ = "ai_staff_requests"
    user_id: Mapped[int] = mapped_column(ForeignKey("ai_users.id"), primary_key=True)
    scope: Mapped[str] = mapped_column(String(200))
    evidence_reference: Mapped[str] = mapped_column(String(500))


class ListingVersion(Base):
    __tablename__ = "ai_listing_versions"
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("ai_listings.id"), primary_key=True
    )
    version: Mapped[int] = mapped_column(primary_key=True)
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class RoundControl(Base):
    __tablename__ = "ai_round_controls"
    round_id: Mapped[int] = mapped_column(ForeignKey("ai_rounds.id"), primary_key=True)
    scope: Mapped[str] = mapped_column(String(200))
    listing_ids: Mapped[list] = mapped_column(JSON)
    tie_seed: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class RoundParticipation(Base):
    __tablename__ = "ai_round_participation"
    round_id: Mapped[int] = mapped_column(ForeignKey("ai_rounds.id"), primary_key=True)
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("ai_users.id"), primary_key=True
    )
    authorized_by: Mapped[int] = mapped_column(ForeignKey("ai_users.id"))
    evidence_reference: Mapped[str] = mapped_column(String(500))
    authorized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class AuditEvent(Base):
    __tablename__ = "ai_audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("ai_users.id"))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SkillVersion(Base):
    __tablename__ = "ai_skill_versions"
    skill_id: Mapped[int] = mapped_column(ForeignKey("ai_skills.id"), primary_key=True)
    source_version: Mapped[str] = mapped_column(String(100), primary_key=True)
    details: Mapped[dict] = mapped_column(JSON)


class SeatEvidence(Base):
    __tablename__ = "ai_seat_evidence"
    round_id: Mapped[int] = mapped_column(ForeignKey("ai_rounds.id"), primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("ai_listings.id"), primary_key=True
    )
    version: Mapped[int] = mapped_column(primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class PolicyProvenance(Base):
    __tablename__ = "ai_policy_provenance"
    document_id: Mapped[int] = mapped_column(
        ForeignKey("ai_policy_documents.id"), primary_key=True
    )
    details: Mapped[dict] = mapped_column(JSON)


class LoginSession(Base):
    __tablename__ = "ai_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("ai_users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Invitation(Base):
    __tablename__ = "ai_invitations"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("ai_users.id"), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Profile(Base):
    __tablename__ = "ai_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("ai_users.id"), primary_key=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Skill(Base):
    __tablename__ = "ai_skills"
    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_id: Mapped[str] = mapped_column(String(512), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(500))
    source_version: Mapped[str] = mapped_column(String(100))
    related: Mapped[list] = mapped_column(JSON, default=list)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    merged_into: Mapped[int | None] = mapped_column(
        ForeignKey("ai_skills.id"), nullable=True
    )


class Listing(Base):
    __tablename__ = "ai_listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("ai_users.id"))
    source_url: Mapped[str] = mapped_column(String(2048), unique=True)
    details: Mapped[dict] = mapped_column(JSON)


class Occupation(Base):
    __tablename__ = "ai_occupations"
    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_id: Mapped[str] = mapped_column(String(512), unique=True)
    name: Mapped[str] = mapped_column(String(300))
    source_version: Mapped[str] = mapped_column(String(200))
    source_record: Mapped[dict] = mapped_column(JSON)


class Document(Base):
    __tablename__ = "ai_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("ai_users.id"))
    filename: Mapped[str] = mapped_column(String(200))
    storage_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pages: Mapped[list] = mapped_column(JSON)


class Evidence(Base):
    __tablename__ = "ai_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("ai_users.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_documents.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(30))
    value: Mapped[str] = mapped_column(String(200))
    skill_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_skills.id"), nullable=True
    )
    excerpt: Mapped[str] = mapped_column(Text)
    section: Mapped[str] = mapped_column(String(100))
    page: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(30))
    context: Mapped[str] = mapped_column(String(30), default="mentioned")
    status: Mapped[str] = mapped_column(String(30), default="needs_review")
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("ai_users.id"), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PolicyDocument(Base):
    __tablename__ = "ai_policy_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    scope: Mapped[str] = mapped_column(String(200))
    effective_date: Mapped[str] = mapped_column(String(30))
    version: Mapped[str] = mapped_column(String(100))
    source_url: Mapped[str] = mapped_column(String(2048))


class Passage(Base):
    __tablename__ = "ai_passages"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("ai_policy_documents.id"))
    section: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(
        Vector(384).with_variant(JSON, "sqlite"), nullable=True
    )
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Policy(Base):
    __tablename__ = "ai_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict] = mapped_column(JSON)
    document_ids: Mapped[list] = mapped_column(JSON, default=list)
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("ai_users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Round(Base):
    __tablename__ = "ai_rounds"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    policy_id: Mapped[int] = mapped_column(ForeignKey("ai_policies.id"))


class Capacity(Base):
    __tablename__ = "ai_capacities"
    round_id: Mapped[int] = mapped_column(ForeignKey("ai_rounds.id"), primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("ai_listings.id"), primary_key=True
    )
    seats: Mapped[int] = mapped_column(Integer)
    confirmed_by: Mapped[int] = mapped_column(ForeignKey("ai_users.id"))
    confirmation_reference: Mapped[str] = mapped_column(String(500))


class Choice(Base):
    __tablename__ = "ai_choices"
    round_id: Mapped[int] = mapped_column(ForeignKey("ai_rounds.id"), primary_key=True)
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("ai_users.id"), primary_key=True
    )
    listing_ids: Mapped[list] = mapped_column(JSON)


class AgentCase(Base):
    __tablename__ = "ai_cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("ai_users.id"))
    round_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_rounds.id"), nullable=True
    )
    policy_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_policies.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), default="created")
    revision: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(40))


class Activity(Base):
    __tablename__ = "ai_activity"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(String(50), index=True)
    step: Mapped[str] = mapped_column(String(80))
    tool: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[dict] = mapped_column(JSON)
    next_action: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Draft(Base):
    __tablename__ = "ai_drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("ai_rounds.id"))
    policy_id: Mapped[int] = mapped_column(ForeignKey("ai_policies.id"))
    revision: Mapped[int] = mapped_column(Integer)
    result: Mapped[dict] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    approval_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("ai_users.id"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class State(Base):
    __tablename__ = "ai_state"
    id: Mapped[int] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


def database(url=None, test=False):
    url = url or os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://allocate:allocate@localhost:55432/allocateai",
    )
    if url.startswith("sqlite") and not test:
        raise RuntimeError("Production requires PostgreSQL; SQLite is only for tests.")
    if url in ("sqlite://", "sqlite:///:memory:"):
        options = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    elif url.startswith("sqlite"):
        # HTTP requests run concurrently. A file database needs one checked-out connection per request.
        options = {"connect_args": {"check_same_thread": False, "timeout": 10}}
    else:
        options = {"pool_pre_ping": True}
    engine = create_engine(url, **options)
    if test:
        Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def revision(db, bump=False):
    row = db.get(State, 1, with_for_update=bump)
    if bump:
        row.revision += 1
    return row.revision
