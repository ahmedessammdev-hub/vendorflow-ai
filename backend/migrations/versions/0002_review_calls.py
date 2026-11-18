"""Record replay-safe model attempts per submission and stage."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("llm_call") as batch:
        batch.alter_column("latency_ms", existing_type=sa.Integer(), nullable=True)
    op.add_column("llm_call", sa.Column("request_version", sa.Integer()))
    op.add_column("llm_call", sa.Column("attempt", sa.Integer()))
    op.add_column("llm_call", sa.Column("validated_output", sa.JSON()))
    op.create_index(
        "uq_llm_call_attempt",
        "llm_call",
        ["request_id", "request_version", "node", "attempt"],
        unique=True,
    )


def downgrade() -> None:
    missing_latency = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM llm_call WHERE latency_ms IS NULL")
    )
    if missing_latency:
        raise RuntimeError(
            "The previous schema cannot represent calls with unknown latency."
        )
    with op.batch_alter_table("llm_call") as batch:
        batch.alter_column("latency_ms", existing_type=sa.Integer(), nullable=False)
    op.drop_index("uq_llm_call_attempt", table_name="llm_call")
    for name in ("validated_output", "attempt", "request_version"):
        op.drop_column("llm_call", name)
