import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Engine, select, update

from app.agents.schemas import Reconcile
from app.domain.enums import Status
from app.domain.models import RequestView
from app.integration.jira_client import DeliveryError, Issue, JiraClient
from app.persistence import repositories as repo
from app.persistence.database import write_transaction
from app.persistence.tables import jira_operation as ops
from app.persistence.tables import review_decision, timestamp


@dataclass(frozen=True)
class Claim:
    request: RequestView
    attempts: int
    search_first: bool
    allow_create: bool
    mode: str
    site: str | None


class Dispatcher:
    def __init__(
        self,
        engine: Engine,
        clients: dict[str, JiraClient],
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.engine = engine
        self.clients = clients
        self.sleep = sleep

    def claim(self, key: UUID, manual: Reconcile | None = None) -> Claim | None:
        with write_transaction(self.engine) as conn:
            current = repo.get(conn, key)
            if manual:
                repo.check_version(current, manual.expected_version)
            row = (
                conn.execute(select(ops).filter_by(request_id=str(key)))
                .mappings()
                .one_or_none()
            )
            allowed = {"FAILED", "UNCERTAIN"} if manual else {"PENDING"}
            state = Status.JIRA_FAILED if manual else Status.JIRA_PENDING
            if row is None or row["status"] not in allowed or current.status != state:
                if manual:
                    raise repo.Conflict(
                        "This operation is not awaiting reconciliation.", current
                    )
                return None
            approved = conn.scalar(
                select(review_decision.c.id).filter_by(
                    request_id=str(key), action="approve"
                )
            )
            if approved is None:
                if manual:
                    raise repo.Conflict("A persisted approval is required.", current)
                return None
            if row["retry_at"] and datetime.fromisoformat(
                row["retry_at"]
            ) > datetime.now(UTC):
                if manual:
                    raise repo.Conflict("Wait until the Jira retry time.", current)
                return None
            client = self.clients.get(row["mode"])
            site = row["site"] or (client.site if client else None)
            changed = conn.execute(
                update(ops)
                .filter_by(id=row["id"], status=row["status"])
                .values(status="IN_FLIGHT", site=site, retry_at=None)
            )
            if changed.rowcount != 1:
                return None
            if manual:
                current = repo.transition(
                    conn,
                    current,
                    Status.JIRA_PENDING,
                    "reviewer",
                    manual.model_dump(exclude={"expected_version"}),
                )
            return Claim(
                current,
                row["attempts"],
                bool(manual or row["attempts"]),
                row["status"] != "UNCERTAIN"
                or bool(manual and manual.checked_jira_and_no_issue_exists),
                row["mode"],
                site,
            )

    def finish(
        self,
        key: UUID,
        status: str,
        *,
        error: str | None = None,
        issue: Issue | None = None,
        delay: float | None = None,
    ) -> None:
        with write_transaction(self.engine) as conn:
            changed = conn.execute(
                update(ops)
                .filter_by(request_id=str(key), status="IN_FLIGHT")
                .values(
                    status=status,
                    last_error=error,
                    last_checked_at=timestamp(),
                    issue_key=issue.key if issue else None,
                    issue_id=issue.id if issue else None,
                    retry_at=(datetime.now(UTC) + timedelta(seconds=delay)).isoformat()
                    if delay
                    else None,
                )
            )
            if changed.rowcount:
                target = Status.JIRA_CREATED if issue else Status.JIRA_FAILED
                repo.transition(
                    conn,
                    repo.get(conn, key),
                    target,
                    "system",
                    {
                        "operation_status": status,
                        "issue_key": issue.key if issue else None,
                    },
                )

    def poll(self, key: UUID, client: JiraClient) -> None:
        for delay in (2, 5, 15, 30):
            self.sleep(delay)
            try:
                issue = client.search(key)
            except DeliveryError as exc:
                self.finish(key, "UNCERTAIN", error=str(exc), delay=exc.retry_after)
                return
            if issue:
                self.finish(key, "CREATED", issue=issue)
                return
        self.finish(
            key,
            "UNCERTAIN",
            error="Issue creation is unconfirmed. Check Jira before retrying.",
        )

    def deliver(self, claim: Claim) -> None:
        key = claim.request.id
        client = self.clients.get(claim.mode)
        if client is None or (claim.site and client.site != claim.site):
            self.finish(
                key,
                "UNCERTAIN" if claim.attempts else "FAILED",
                error="Restore the original Jira integration settings.",
            )
            return
        for index in range(3):
            if claim.search_first or index:
                try:
                    issue = client.search(key)
                except DeliveryError as exc:
                    self.finish(key, "UNCERTAIN", error=str(exc), delay=exc.retry_after)
                    return
                if issue:
                    self.finish(key, "CREATED", issue=issue)
                    return
                if not claim.allow_create:
                    self.finish(
                        key,
                        "UNCERTAIN",
                        error="No indexed issue found. Reviewer confirmation is required for a new attempt.",
                    )
                    return
            with write_transaction(self.engine) as conn:
                changed = conn.execute(
                    update(ops)
                    .filter_by(
                        request_id=str(key),
                        status="IN_FLIGHT",
                        attempts=claim.attempts + index,
                    )
                    .values(attempts=ops.c.attempts + 1)
                )
                if not changed.rowcount:
                    return
            try:
                issue = client.create(claim.request)
            except DeliveryError as exc:
                if exc.uncertain:
                    self.poll(key, client)
                    return
                if exc.retry_after is None or index == 2 or exc.retry_after > 30:
                    self.finish(key, "FAILED", error=str(exc), delay=exc.retry_after)
                    return
                self.sleep(exc.retry_after)
            else:
                self.finish(key, "CREATED", issue=issue)
                return

    def dispatch(self, key: UUID) -> None:
        claim = self.claim(key)
        if claim:
            self.deliver(claim)

    def recover(self) -> None:
        with self.engine.begin() as conn:
            interrupted = conn.scalars(
                select(ops.c.request_id).filter_by(status="IN_FLIGHT")
            ).all()
            pending = conn.scalars(
                select(ops.c.request_id).filter_by(status="PENDING")
            ).all()
        for item in interrupted:
            self.finish(
                UUID(item),
                "UNCERTAIN",
                error="Dispatcher stopped during delivery. Reconcile the request marker.",
            )
        for item in pending:
            self.dispatch(UUID(item))
