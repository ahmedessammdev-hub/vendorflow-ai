from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.domain.enums import Status
from app.domain.models import (
    ConflictView,
    CreateRequest,
    EditRequest,
    RequestList,
    RequestView,
    Versioned,
)
from app.services.requests import RequestService

router = APIRouter(prefix="/requests", tags=["requests"])


def service(request: Request) -> RequestService:
    return RequestService(request.app.state.engine)


Service = Annotated[RequestService, Depends(service)]


@router.post("", status_code=201)
def create_request(body: CreateRequest, requests: Service) -> RequestView:
    return requests.create(body)


@router.get("")
def list_requests(requests: Service, status: Status | None = None) -> RequestList:
    return requests.list_requests(status)


@router.get("/{request_id}")
def get_request(request_id: UUID, requests: Service) -> RequestView:
    return requests.get(request_id)


@router.patch("/{request_id}", responses={409: {"model": ConflictView}})
def edit_request(request_id: UUID, body: EditRequest, requests: Service) -> RequestView:
    return requests.edit(request_id, body)


@router.post(
    "/{request_id}/submit",
    responses={202: {"model": RequestView}, 409: {"model": ConflictView}},
)
def submit_request(
    request_id: UUID, body: Versioned, requests: Service, response: Response
) -> RequestView:
    result = requests.submit(request_id, body.expected_version)
    if result.status == Status.UNDER_REVIEW:
        response.status_code = 202
    return result
