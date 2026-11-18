from uuid import UUID

from sqlalchemy import Engine, insert, select

from app.agents.schemas import AssessmentView, HumanDecision, JiraView, RequestDetail
from app.domain.enums import Status
from app.domain.models import RequestView
from app.persistence import repositories as repo
from app.persistence.database import write_transaction
from app.persistence.tables import assessment, jira_operation, review_decision


def detail(engine: Engine, key: UUID) -> RequestDetail:
    with engine.begin() as conn:
        request = repo.get(conn, key)
        result = RequestDetail(**request.model_dump())
        if request.status in {Status.DRAFT, Status.NEEDS_CHANGES, Status.SUBMITTED}:
            return result
        operation = (
            conn.execute(select(jira_operation).filter_by(request_id=str(key)))
            .mappings()
            .one_or_none()
        )
        if operation:
            issue_key = operation["issue_key"]
            link = None
            if (
                operation["mode"] == "live"
                and operation["status"] == "CREATED"
                and operation["site"]
                and issue_key
                and not issue_key.startswith("SIM-")
            ):
                link = f"{operation['site']}/browse/{issue_key}"
            result.jira = JiraView.model_validate(
                {k: operation[k] for k in JiraView.model_fields if k != "issue_url"}
                | {"issue_url": link}
            )
        row = (
            conn.execute(
                select(assessment)
                .filter_by(request_id=str(key))
                .order_by(assessment.c.request_version.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        if row and row["ai_status"]:
            result.assessment = AssessmentView.model_validate(
                {k: row[k] for k in AssessmentView.model_fields}
            )
        return result


def decide(
    engine: Engine, key: UUID, decision: HumanDecision, jira_mode: str
) -> RequestView:
    with write_transaction(engine) as conn:
        current = repo.get(conn, key)
        repo.check_version(current, decision.expected_version)
        if current.status != Status.AWAITING_APPROVAL:
            raise repo.Conflict(
                "A human decision requires a request awaiting approval.", current
            )
        payload = decision.model_dump(exclude={"expected_version"})
        conn.execute(
            insert(review_decision).values(
                request_id=str(key), request_version=current.version, **payload
            )
        )
        targets = {
            "approve": Status.APPROVED,
            "reject": Status.REJECTED,
            "request_changes": Status.NEEDS_CHANGES,
        }
        result = repo.transition(
            conn, current, targets[decision.action], "reviewer", payload
        )
        if decision.action == "approve":
            conn.execute(
                insert(jira_operation).values(
                    request_id=str(key),
                    mode=jira_mode,
                    status="PENDING",
                    marker=f"vf-{key}",
                )
            )
            result = repo.transition(
                conn, result, Status.JIRA_PENDING, "system", {"mode": jira_mode}
            )
        return result
