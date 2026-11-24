"""One-time activation for placement-cell imported participant accounts."""

from alembic import op
from app.db import Invitation

revision = "004_invitations"
down_revision = "003_evidence_review"
branch_labels = None
depends_on = None


def upgrade():
    Invitation.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    Invitation.__table__.drop(op.get_bind(), checkfirst=True)
