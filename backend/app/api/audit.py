from uuid import UUID

from fastapi import APIRouter

from app.api.requests import Service
from app.domain.models import AuditView

router = APIRouter(tags=["audit"])


@router.get("/requests/{request_id}/audit")
def audit_history(request_id: UUID, requests: Service) -> list[AuditView]:
    return requests.audit(request_id)
