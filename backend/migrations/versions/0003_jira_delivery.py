"""Persist the simulated external issue, live destination and retry deadline."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "simulated_issue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("marker", sa.String(80), nullable=False),
    )
    op.add_column("jira_operation", sa.Column("site", sa.String(253)))
    op.add_column("jira_operation", sa.Column("retry_at", sa.String(40)))


def downgrade() -> None:
    op.drop_column("jira_operation", "retry_at")
    op.drop_column("jira_operation", "site")
    op.drop_table("simulated_issue")
