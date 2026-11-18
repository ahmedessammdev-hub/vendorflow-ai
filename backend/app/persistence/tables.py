from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

from app.domain.enums import Category, Criticality, EvidenceKind, RiskBand, Status

metadata = MetaData()


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def request_fk() -> Column[str]:
    return Column(
        "request_id", String(36), ForeignKey("vendor_request.id"), nullable=False
    )


def choices(column: str, values: list[str]) -> CheckConstraint:
    allowed = ", ".join(repr(value) for value in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=f"valid_{column}")


vendor_request = Table(
    "vendor_request",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("vendor_name", String(120), nullable=False),
    Column("service_category", String(24), nullable=False),
    Column("business_criticality", String(12), nullable=False),
    Column("sensitive_data_access", Boolean(create_constraint=True), nullable=False),
    Column("requester_department", String(120), nullable=False),
    Column("service_description", Text, nullable=False),
    Column("status", String(24), nullable=False, index=True),
    Column("version", Integer, nullable=False),
    Column("created_at", String(40), nullable=False, default=timestamp),
    Column("updated_at", String(40), nullable=False, default=timestamp),
    choices("status", [s.value for s in Status]),
    choices("service_category", [s.value for s in Category]),
    choices("business_criticality", [s.value for s in Criticality]),
    CheckConstraint("version >= 1", name="positive_version"),
)

evidence = Table(
    "evidence",
    metadata,
    Column("id", Integer, primary_key=True),
    request_fk(),
    Column("kind", String(32), nullable=False),
    Column("present", Boolean(create_constraint=True), nullable=False),
    Column("pointer", String(120)),
    UniqueConstraint("request_id", "kind"),
    choices("kind", [e.value for e in EvidenceKind]),
)

assessment = Table(
    "assessment",
    metadata,
    Column("id", Integer, primary_key=True),
    request_fk(),
    Column("request_version", Integer, nullable=False),
    Column("score", Integer, nullable=False),
    Column("band", String(12), nullable=False),
    Column("factors", JSON, nullable=False),
    Column("summary", JSON),
    Column("recommendation", JSON),
    Column("ai_status", String(24)),
    Column("model", String(200)),
    Column("prompt_version", String(64)),
    Column("created_at", String(40), nullable=False, default=timestamp),
    choices("band", [b.value for b in RiskBand]),
    UniqueConstraint("request_id", "request_version"),
)

review_decision = Table(
    "review_decision",
    metadata,
    Column("id", Integer, primary_key=True),
    request_fk(),
    Column("request_version", Integer, nullable=False),
    Column("reviewer_label", String(120), nullable=False),
    Column("action", String(24), nullable=False),
    Column("reason", Text, nullable=False),
    Column("created_at", String(40), nullable=False, default=timestamp),
    choices("action", ["approve", "reject", "request_changes"]),
    UniqueConstraint("request_id", "request_version"),
)

jira_operation = Table(
    "jira_operation",
    metadata,
    Column("id", Integer, primary_key=True),
    request_fk(),
    Column("mode", String(16), nullable=False),
    Column("status", String(16), nullable=False),
    Column("issue_key", String(128)),
    Column("issue_id", String(128)),
    Column("marker", String(80), nullable=False),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("last_error", Text),
    Column("last_checked_at", String(40)),
    Column("site", String(253)),
    Column("retry_at", String(40)),
    UniqueConstraint("request_id"),
    choices("mode", ["simulation", "live"]),
    choices("status", ["PENDING", "IN_FLIGHT", "CREATED", "FAILED", "UNCERTAIN"]),
)

simulated_issue = Table(
    "simulated_issue",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("marker", String(80), nullable=False),
)

audit_event = Table(
    "audit_event",
    metadata,
    Column("id", Integer, primary_key=True),
    request_fk(),
    Column("actor_type", String(32), nullable=False),
    Column("event_type", String(50), nullable=False),
    Column("from_status", String(24)),
    Column("to_status", String(24), nullable=False),
    Column("detail", JSON, nullable=False),
    Column("created_at", String(40), nullable=False, default=timestamp),
)

llm_call = Table(
    "llm_call",
    metadata,
    Column("id", Integer, primary_key=True),
    request_fk(),
    Column("request_version", Integer),
    Column("attempt", Integer),
    Column("validated_output", JSON),
    Column("node", String(80), nullable=False),
    Index(
        "uq_llm_call_attempt",
        "request_id",
        "request_version",
        "node",
        "attempt",
        unique=True,
    ),
    Column("model", String(200), nullable=False),
    Column("prompt_version", String(64), nullable=False),
    Column("latency_ms", Integer),
    Column("tokens_in", Integer),
    Column("tokens_out", Integer),
    Column("outcome", String(32), nullable=False),
    Column("failure_reason", String(48)),
    Column("created_at", String(40), nullable=False, default=timestamp),
)
