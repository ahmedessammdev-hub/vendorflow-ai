from collections import deque
from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Engine, insert, select

from app.domain.models import RequestView
from app.integration.jira_client import DeliveryError, Issue
from app.persistence.database import write_transaction
from app.persistence.tables import simulated_issue


class SimulatedJira:
    site: str | None = None

    def __init__(self, engine: Engine, *, test_faults: Iterable[str] = ()) -> None:
        self.engine = engine
        self.faults = deque(test_faults)

    def create(self, request: RequestView) -> Issue:
        fault = self.faults.popleft() if self.faults else None
        if fault == "429":
            raise DeliveryError("Simulated rate limit.", retry_after=1.0)
        if fault in {"timeout", "500"}:
            raise DeliveryError("Simulated ambiguous response.", uncertain=True)
        with write_transaction(self.engine) as conn:
            number = conn.execute(
                insert(simulated_issue)
                .values(marker=f"vf-{request.id}")
                .returning(simulated_issue.c.id)
            ).scalar_one()
        if fault == "timeout_after_create":
            raise DeliveryError("Simulated lost acknowledgement.", uncertain=True)
        return Issue(f"SIM-{number}", str(number))

    def search(self, key: UUID) -> Issue | None:
        with self.engine.begin() as conn:
            ids = conn.scalars(
                select(simulated_issue.c.id).filter_by(marker=f"vf-{key}").limit(2)
            ).all()
        if len(ids) > 1:
            raise DeliveryError("Multiple simulated issues found.", uncertain=True)
        return Issue(f"SIM-{ids[0]}", str(ids[0])) if ids else None
