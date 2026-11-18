from uuid import UUID, uuid4

from sqlalchemy import Engine, insert

from app.domain.enums import Status
from app.domain.models import (
    AuditView,
    CreateRequest,
    EditRequest,
    RequestList,
    RequestView,
    VendorData,
)
from app.persistence import repositories as repo
from app.persistence.database import write_transaction
from app.persistence.tables import assessment


class RequestService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create(self, data: CreateRequest) -> RequestView:
        with write_transaction(self.engine) as conn:
            fields = VendorData.model_validate(
                data.model_dump(exclude={"expected_version"})
            )
            return repo.create(conn, uuid4(), fields)

    def get(self, key: UUID) -> RequestView:
        with self.engine.begin() as conn:
            return repo.get(conn, key)

    def list_requests(self, status: Status | None) -> RequestList:
        with self.engine.begin() as conn:
            return repo.list_requests(conn, status)

    def audit(self, key: UUID) -> list[AuditView]:
        with self.engine.begin() as conn:
            return repo.history(conn, key)

    def edit(self, key: UUID, patch: EditRequest) -> RequestView:
        with write_transaction(self.engine) as conn:
            current = repo.get(conn, key)
            repo.check_version(current, patch.expected_version)
            if current.status not in {Status.DRAFT, Status.NEEDS_CHANGES}:
                raise repo.Conflict(
                    "Only drafts and returned requests can be edited.", current
                )
            values = patch.model_dump(
                exclude_unset=True, exclude={"expected_version", "evidence"}
            )
            repo.write(conn, current, values)
            if patch.evidence is not None:
                repo.replace_evidence(conn, key, patch.evidence)
            changed = sorted(patch.model_fields_set - {"expected_version"})
            repo.audit(
                conn,
                key,
                "edited",
                "requester",
                current.status,
                current.status,
                {"fields": changed, "version": current.version + 1},
            )
            return repo.get(conn, key)

    def submit(self, key: UUID, expected_version: int) -> RequestView:
        with write_transaction(self.engine) as conn:
            current = repo.get(conn, key)
            repo.check_version(current, expected_version)
            submitted = repo.transition(
                conn, current, Status.SUBMITTED, "requester", {}
            )
            if submitted.missing_evidence:
                return repo.transition(
                    conn,
                    submitted,
                    Status.NEEDS_CHANGES,
                    "system",
                    {"missing_evidence": submitted.missing_evidence},
                )
            result = repo.transition(conn, submitted, Status.UNDER_REVIEW, "system", {})
            conn.execute(
                insert(assessment).values(
                    request_id=str(key),
                    request_version=result.version,
                    **result.risk.model_dump(mode="json"),
                )
            )
            return result
