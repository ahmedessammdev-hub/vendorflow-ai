from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from app.persistence.tables import jira_operation, llm_call, vendor_request

router = APIRouter(tags=["metrics"])


class WorkspaceMetrics(BaseModel):
    requests: dict[str, int]
    jira: dict[str, int]
    calls: int
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    tokens_in: int | None
    tokens_out: int | None


@router.get("/metrics")
def metrics(request: Request) -> WorkspaceMetrics:
    with request.app.state.engine.connect() as conn:
        requests = {
            key: count
            for key, count in conn.execute(
                select(vendor_request.c.status, func.count()).group_by(
                    vendor_request.c.status
                )
            )
        }
        jira = {
            key: count
            for key, count in conn.execute(
                select(jira_operation.c.status, func.count()).group_by(
                    jira_operation.c.status
                )
            )
        }
        calls, tokens_in, tokens_out = conn.execute(
            select(
                func.count(),
                func.sum(llm_call.c.tokens_in),
                func.sum(llm_call.c.tokens_out),
            ).select_from(llm_call)
        ).one()
        latencies = conn.scalars(
            select(llm_call.c.latency_ms)
            .where(llm_call.c.latency_ms.is_not(None))
            .order_by(llm_call.c.latency_ms)
        ).all()

    def percentile(p: int) -> int | None:
        return (
            int(latencies[(len(latencies) * p + 99) // 100 - 1]) if latencies else None
        )

    return WorkspaceMetrics(
        requests=requests,
        jira=jira,
        calls=calls,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_p50_ms=percentile(50),
        latency_p95_ms=percentile(95),
    )
