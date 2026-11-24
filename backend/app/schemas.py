from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class Input(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False
    )


class Login(Input):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class Register(Login):
    name: str = Field(min_length=2, max_length=120)
    role: Literal["applicant"] = "applicant"
    activation_token: str | None = Field(default=None, max_length=200)

    @field_validator("password")
    @classmethod
    def strong(cls, v):
        if len(v) < 10:
            raise ValueError("Use at least 10 characters")
        return v

    @field_validator("email")
    @classmethod
    def email_valid(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email")
        return v.lower()


class StaffRequestInput(Input):
    scope: str = Field(min_length=2, max_length=200)
    evidence_reference: str = Field(min_length=5, max_length=500)


class StaffGrantInput(StaffRequestInput):
    role: Literal["company", "placement"]


class ListingApproval(Input):
    expected_version: int = Field(ge=1)
    verification_reference: str = Field(min_length=5, max_length=500)


class ParticipationInput(Input):
    applicant_id: int = Field(gt=0)
    evidence_reference: str = Field(min_length=5, max_length=500)


class ResumeDecision(Input):
    action: Literal["accept", "edit", "reject"]
    value: str | None = Field(default=None, min_length=1, max_length=200)
    skill_id: int | None = None


class ProfileInput(Input):
    education: str | None = Field(default=None, max_length=300)
    qualification: str | None = Field(default=None, max_length=160)
    course: str | None = Field(default=None, max_length=160)
    academic_branch: str | None = Field(default=None, max_length=160)
    graduation_status: str | None = Field(default=None, max_length=100)
    preferred_role: str | None = Field(default=None, max_length=150)
    projects: list[str] = Field(default_factory=list, max_length=20)
    certifications: list[str] = Field(default_factory=list, max_length=20)
    preferred_work_modes: list[Literal["remote", "hybrid", "onsite"]] = Field(
        default_factory=list
    )
    approved_hosted_resume_processing: bool = False
    district: str | None = Field(default=None, max_length=100)
    home_location: str | None = Field(default=None, max_length=100)
    preferred_locations: list[str] = Field(default_factory=list, max_length=20)
    preferred_sectors: list[str] = Field(default_factory=list, max_length=20)
    willing_to_relocate: bool = True
    academic_score: float | None = Field(default=None, ge=0, le=100)
    prior_participation: bool | None = None
    groups: list[
        Literal["SC", "ST", "OBC", "PwD", "women", "rural", "aspirational"]
    ] = Field(default_factory=list)
    consent: bool = False


class SkillInput(Input):
    canonical_id: str = Field(min_length=1, max_length=512)
    name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    category: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=500)
    source_version: str = Field(min_length=1, max_length=100)
    related: list[int] = Field(default_factory=list)
    reviewed: bool = False


class Requirement(Input):
    skill_id: int
    classification: Literal["required", "preferred", "mentioned"]
    excerpt: str = Field(min_length=1, max_length=2000)


class ListingInput(Input):
    title: str = Field(min_length=3, max_length=200)
    organization: str = Field(min_length=2, max_length=200)
    source_name: str = Field(min_length=2, max_length=200)
    source_url: HttpUrl
    location: str | None = Field(default=None, max_length=200)
    work_mode: Literal["onsite", "hybrid", "remote"] | None = None
    sector: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=10, max_length=30000)
    rolling: bool = False
    unresolved_requirements: list[str] = Field(default_factory=list, max_length=100)
    requirements_text: str = Field(default="", max_length=20000)
    requirements: list[Requirement] = Field(default_factory=list, max_length=100)
    mandatory_qualifications: list[str] = Field(default_factory=list, max_length=20)
    stipend: str | None = Field(default=None, max_length=500)
    deadline: date | None = None
    last_verified: date | None = None
    status: Literal["open", "expired", "unverified"] = "unverified"


class ManualEvidence(Input):
    kind: Literal["skill", "qualification", "project", "certification", "experience", "participation"]
    value: str = Field(min_length=1, max_length=200)
    skill_id: int | None = None
    excerpt: str = Field(min_length=1, max_length=2000)
    context: Literal["skills_section", "project", "education", "mentioned"] = (
        "mentioned"
    )


class EvidenceReview(Input):
    status: Literal["verified", "rejected", "not_held"]
    note: str | None = Field(default=None, max_length=1000)


class PolicyDocumentInput(Input):
    title: str = Field(min_length=3, max_length=300)
    scope: str = Field(min_length=2, max_length=200)
    effective_date: date
    version: str = Field(min_length=1, max_length=100)
    publisher: str | None = Field(default=None, max_length=250)
    scheme: str | None = Field(default=None, max_length=120)
    published_on: date | None = None
    effective_until: date | None = None
    source_url: HttpUrl
    sections: dict[str, str] = Field(min_length=1, max_length=100)


class Rules(Input):
    coverage_confirmed: bool = False
    scheme: str | None = Field(default=None, max_length=120)
    effective_date: date | None = None
    require_noc: bool = False
    exclude_prior_participants: bool = False
    minimum_placements: dict[str, int] = Field(default_factory=dict)
    equity_weight: float = Field(default=0, ge=0, le=0.1)
    equity_adjustments: dict[str, float] = Field(default_factory=dict)

    @field_validator("minimum_placements", "equity_adjustments")
    @classmethod
    def groups_valid(cls, v, info):
        if not set(v) <= {"SC", "ST", "OBC", "PwD", "women", "rural", "aspirational"}:
            raise ValueError("Unknown group")
        maximum = 10000 if info.field_name == "minimum_placements" else 1
        if any(not 0 <= n <= maximum for n in v.values()):
            raise ValueError("Value outside allowed range")
        return v


class PolicyInput(Input):
    name: str = Field(min_length=1, max_length=120)
    config: Rules = Field(default_factory=Rules)
    document_ids: list[int] = Field(default_factory=list)


class RoundInput(Input):
    name: str = Field(min_length=1, max_length=120)
    policy_id: int
    scope: str = Field(min_length=2, max_length=200)
    listing_ids: list[int] = Field(min_length=1, max_length=1000)


class CapacityInput(Input):
    listing_id: int
    seats: int = Field(ge=0, le=10000)
    confirmation_reference: str = Field(min_length=5, max_length=500)


class Choices(Input):
    listing_ids: list[int] = Field(max_length=5)

    @field_validator("listing_ids")
    @classmethod
    def unique(cls, v):
        if len(v) != len(set(v)):
            raise ValueError("Choices must be unique")
        return v


class CaseInput(Input):
    round_id: int | None = None
    policy_id: int | None = None
    policy_question: str = Field(default="", max_length=500)


class Acknowledge(Input):
    approved: Literal[True]
    digest: str = Field(min_length=64, max_length=64)


class ExtractionClaim(Input):
    kind: Literal["skill", "qualification", "project", "certification", "experience"]
    value: str = Field(min_length=1, max_length=200)
    excerpt: str = Field(min_length=1, max_length=2000)
    page: int = Field(ge=1)
    context: Literal["skills_section", "project", "education", "mentioned"] = (
        "mentioned"
    )


class Extraction(Input):
    claims: list[ExtractionClaim] = Field(max_length=150)


class ExplanationSelection(Input):
    fact_ids: list[str] = Field(min_length=1, max_length=12)


class ToolCall(Input):
    name: Literal[
        "inspect_resume_evidence",
        "resolve_skill_alias",
        "search_policy",
        "request_human_review",
    ]
    arguments: dict = Field(default_factory=dict)


class RetrievalQuestion(Input):
    question: str = Field(min_length=3, max_length=500)
    policy_id: int
    mode: Literal["keyword", "vector", "hybrid"] = "hybrid"


class ImportedParticipant(Input):
    email: str
    name: str = Field(min_length=2, max_length=120)
    profile: ProfileInput
    evidence: list[ManualEvidence] = Field(default_factory=list)


class ParticipantImport(Input):
    authorized: Literal[True]
    profiles: list[ImportedParticipant] = Field(max_length=200)


class EvidenceReviewOutput(Input):
    verdict: Literal["supported", "review"]
    passage_ids: list[int] = Field(max_length=10)
