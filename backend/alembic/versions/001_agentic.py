"""Real-data schema, vector extension, policy full-text index."""

from alembic import op
from app.db import Base

revision = "001_agentic"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(op.get_bind())
    op.execute(
        "CREATE INDEX IF NOT EXISTS ai_passages_fts ON ai_passages USING gin(to_tsvector('english', content))"
    )


def downgrade():
    Base.metadata.drop_all(op.get_bind())
