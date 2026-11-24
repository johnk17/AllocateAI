"""Separate rejection of evidence from an explicit confirmed-not-held decision."""

from alembic import op
from sqlalchemy import inspect, Column, Text

revision = "003_evidence_review"
down_revision = "002_occupations"
branch_labels = None
depends_on = None


def upgrade():
    if "review_note" not in {
        c["name"] for c in inspect(op.get_bind()).get_columns("ai_evidence")
    }:
        op.add_column("ai_evidence", Column("review_note", Text(), nullable=True))


def downgrade():
    op.drop_column("ai_evidence", "review_note")
