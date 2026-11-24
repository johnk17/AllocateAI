from datetime import timezone
from sqlalchemy import select, func
from .db import (
    Profile,
    Evidence,
    Listing,
    Capacity,
    Choice,
    Round,
    Policy,
    Skill,
    RoundControl,
    SeatEvidence,
    StaffGrant,
    User,
    RoundParticipation,
)
from .engine import eligible, listing_status, fingerprint


def applicant_snapshot(db, applicant_id):
    row = db.get(Profile, applicant_id)
    p = dict(row.details) if row else {}
    claims = list(
        db.scalars(select(Evidence).where(Evidence.applicant_id == applicant_id))
    )
    verified = [e for e in claims if e.status == "verified" and e.reviewed_by]
    accepted = [
        e
        for e in claims
        if e.status in ("self_reported", "resume_supported") or e in verified
    ]
    skills = sorted({e.skill_id for e in accepted if e.kind == "skill" and e.skill_id})
    related = set()
    accepted_skill_names = set()
    for sid in skills:
        skill = db.get(Skill, sid)
        if skill:
            related.update(skill.related)
            accepted_skill_names.add(skill.name.casefold())
    return {
        "id": applicant_id,
        **p,
        "skills": skills,
        "accepted_skill_names": sorted(accepted_skill_names),
        "evidence_version": fingerprint(sorted(
            (e.id, e.status, e.source, e.reviewed_by, e.document_id) for e in claims
        )),
        "reviewed_skills": sorted(
            {e.skill_id for e in verified if e.kind == "skill" and e.skill_id}
        ),
        "prior_participation_confirmed": next(
            (e.value.casefold() == "yes" for e in verified if e.kind == "participation"
             and e.value.casefold() in ("yes", "no")), None
        ),
        "noc_confirmed": any(
            e.kind == "qualification" and e.value.strip().casefold() == "noc"
            for e in verified
        ),
        "related_skills": sorted(related - set(skills)),
        "pending_skills": sorted(
            {
                e.skill_id
                for e in claims
                if e.kind == "skill" and e.status == "needs_review" and e.skill_id
            }
            - set(skills)
        ),
        "qualifications": sorted(
            {e.value for e in verified if e.kind == "qualification"}
        ),
        "rejected_qualifications": sorted(
            {
                e.value
                for e in claims
                if e.kind == "qualification" and e.status == "not_held"
            }
        ),
    }


def round_snapshot(db, round_id):
    round_ = db.get(Round, round_id)
    if not round_:
        raise ValueError("Round not found")
    policy = db.get(Policy, round_.policy_id)
    if not policy or not policy.approved_by:
        raise ValueError("An admin-approved policy configuration is required")
    control = db.get(RoundControl, round_id)
    if not control:
        raise ValueError(
            "Legacy round has no authorized role scope. Create a new scoped round."
        )
    choices = list(
        db.scalars(
            select(Choice)
            .where(Choice.round_id == round_id)
            .order_by(Choice.applicant_id)
        )
    )
    if not choices:
        raise ValueError("No participating applicants have submitted choices")
    applicants = []
    for choice in choices:
        participation = db.get(RoundParticipation, (round_id, choice.applicant_id))
        if not participation:
            raise ValueError("An applicant is missing current round authorization")
        authorizer = db.get(User, participation.authorized_by)
        membership = db.get(StaffGrant, participation.authorized_by)
        if not authorizer or not (
            authorizer.role == "admin"
            or (
                authorizer.role == "placement"
                and membership
                and membership.role == "placement"
                and membership.scope.casefold() == control.scope.casefold()
            )
        ):
            raise ValueError("Participation authorization is no longer valid")
        a = applicant_snapshot(db, choice.applicant_id)
        if not a.get("consent"):
            raise ValueError(f"Applicant {a['id']} has not consented to participation")
        if not set(choice.listing_ids) <= set(control.listing_ids):
            raise ValueError(
                "A participant must reconfirm choices in the current scope"
            )
        applicants.append(
            {
                key: a[key]
                for key in (
                    "id",
                    "skills",
                    "reviewed_skills",
                    "pending_skills",
                    "evidence_version",
                    "qualifications",
                    "rejected_qualifications",
                    "noc_confirmed",
                    "consent",
                )
                if key in a
            }
            | {
                key: a.get(key)
                for key in (
                    "prior_participation_confirmed",
                    "willing_to_relocate",
                    "home_location",
                )
            }
            | {
                "rankings": choice.listing_ids,
                "participation_authorized_by": participation.authorized_by,
                "participation_version": participation.authorized_at.isoformat(),
            }
        )
    capacities = [db.get(Capacity, (round_id, lid)) for lid in control.listing_ids]
    if not capacities or any(cap is None for cap in capacities):
        raise ValueError(
            "No employer-confirmed seat counts. Recommendation mode is available."
        )
    listings = []
    for cap in capacities:
        listing = db.get(Listing, cap.listing_id)
        version = db.scalar(
            select(func.max(SeatEvidence.version)).where(
                SeatEvidence.round_id == round_id, SeatEvidence.listing_id == listing.id
            )
        )
        attestation = (
            db.get(SeatEvidence, (round_id, listing.id, version)) if version else None
        )
        approver = db.get(User, cap.confirmed_by)
        grant = db.get(StaffGrant, cap.confirmed_by)
        authorized = approver and grant and grant.role == approver.role and (
            grant.scope.casefold() == control.scope.casefold() and
            (grant.role == "placement" or (grant.role == "company" and listing.owner_id == approver.id))
        )
        if (
            not authorized
            or not attestation
            or attestation.payload["revoked"]
            or attestation.payload["listing_version"]
            != listing.details.get("listing_version", 1)
            or listing_status(listing.details) != "open"
        ):
            raise ValueError(
                "An in-scope listing or capacity authorization is stale, closed or revoked"
            )
        listings.append(
            {
                "id": listing.id,
                **listing.details,
                "capacity": cap.seats,
                "confirmation_reference": cap.confirmation_reference,
                "capacity_version": version,
                "confirmed_by": cap.confirmed_by,
                "confirmed_at": attestation.confirmed_at.replace(tzinfo=timezone.utc).isoformat(),
            }
        )
    return applicants, listings, policy


def unresolved_case(db, case):
    a = applicant_snapshot(db, case.applicant_id)
    if not a.get("consent"):
        return ["Participant consent is missing"]
    if not case.round_id:
        pending = list(
            db.scalars(
                select(Evidence).where(
                    Evidence.applicant_id == case.applicant_id,
                    Evidence.status == "needs_review",
                )
            )
        )
        return [f"Evidence {e.id} needs review" for e in pending]
    round_ = db.get(Round, case.round_id)
    policy = db.get(Policy, round_.policy_id)
    choices = db.get(Choice, (case.round_id, case.applicant_id))
    if not choices or not choices.listing_ids:
        return ["No ranked choices submitted for this round"]
    result = []
    ambiguous = list(
        db.scalars(
            select(Evidence).where(
                Evidence.applicant_id == case.applicant_id,
                Evidence.kind == "skill",
                Evidence.skill_id.is_(None),
                Evidence.status == "needs_review",
            )
        )
    )
    result.extend(
        f"Ambiguous canonical skill claim {e.id} needs review" for e in ambiguous
    )
    for lid in choices.listing_ids:
        listing = db.get(Listing, lid)
        if not listing:
            continue
        check = eligible(
            a,
            {"id": lid, **listing.details},
            policy.config | {"policy_version": policy.id},
        )
        if check["status"] == "needs_review":
            result.extend(check["reasons"])
    return result
