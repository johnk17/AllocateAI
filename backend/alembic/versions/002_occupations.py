"""Retain occupational source concepts separately from measured listing demand."""

from alembic import op
from app.db import Occupation

revision = "002_occupations"
down_revision = "001_agentic"
branch_labels = None
depends_on = None


def upgrade():
    Occupation.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    Occupation.__table__.drop(op.get_bind(), checkfirst=True)
