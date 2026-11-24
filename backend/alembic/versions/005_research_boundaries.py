"""Add scoped grants, version history and frozen rounds without changing existing rows."""

from alembic import op
from app.db import (
    AuditEvent,
    ListingVersion,
    PolicyProvenance,
    RoundControl,
    RoundParticipation,
    SeatEvidence,
    SkillVersion,
    StaffGrant,
    StaffRequest,
)

revision = "005_research_boundaries"
down_revision = "004_invitations"
branch_labels = None
depends_on = None

tables = (
    StaffGrant,
    StaffRequest,
    ListingVersion,
    RoundControl,
    SeatEvidence,
    PolicyProvenance,
    RoundParticipation,
    AuditEvent,
    SkillVersion,
)


def upgrade():
    for model in tables:
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    for model in reversed(tables):
        model.__table__.drop(op.get_bind(), checkfirst=True)
