from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.domain.enums import Status
from app.domain.models import CreateRequest
from app.persistence.database import make_engine, migrate, write_transaction
from app.services.requests import RequestService


def test_migration_constraints_and_atomic_submit(tmp_path: Path) -> None:
    engine = make_engine(tmp_path / "rollback.sqlite")
    try:
        migrate(engine)
        migrate(engine)
        schema = inspect(engine)
        for table, keys in {
            "evidence": ["request_id", "kind"],
            "assessment": ["request_id", "request_version"],
            "review_decision": ["request_id", "request_version"],
            "jira_operation": ["request_id"],
        }.items():
            assert keys in [
                constraint["column_names"]
                for constraint in schema.get_unique_constraints(table)
            ]
        service = RequestService(engine)
        draft = service.create(
            CreateRequest.model_validate(
                {
                    "vendor_name": "Demo Supplier",
                    "service_category": "consulting",
                    "business_criticality": "low",
                    "requester_department": "Operations",
                    "sensitive_data_access": False,
                    "service_description": "Synthetic service",
                }
            )
        )
        with write_transaction(engine) as conn:
            conn.exec_driver_sql(
                "CREATE TRIGGER simulate_audit_failure BEFORE INSERT ON audit_event "
                "WHEN NEW.to_status = 'NEEDS_CHANGES' "
                "BEGIN SELECT RAISE(ABORT, 'simulated audit failure'); END"
            )
        with pytest.raises(IntegrityError, match="simulated audit failure"):
            service.submit(draft.id, draft.version)
        assert service.get(draft.id) == draft
        assert [entry.to_status for entry in service.audit(draft.id)] == [Status.DRAFT]
    finally:
        engine.dispose()
