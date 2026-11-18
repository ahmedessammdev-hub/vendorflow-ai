from typing import Literal

from fastapi import APIRouter, Request

from app.api.settings import IntegrationModes, integration_modes

router = APIRouter()


class Health(IntegrationModes):
    status: Literal["ok"] = "ok"


@router.get("/health")
def get_health(request: Request) -> Health:
    return Health(**integration_modes(request.app.state.settings).model_dump())
