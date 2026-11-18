"""Record bounded provider diagnostics without response bodies or credentials."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_call", sa.Column("failure_reason", sa.String(48), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_call", "failure_reason")
