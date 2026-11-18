from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema

from app.domain.enums import Category, Criticality, EvidenceKind, RiskBand, Status

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)
]
Department = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]
Version = Annotated[int, Field(strict=True, ge=1)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Model):
    kind: EvidenceKind
    present: StrictBool
    pointer: (
        Annotated[
            str,
            Field(max_length=120, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*\.(txt|pdf)$"),
        ]
        | None
    ) = None


def distinct_evidence(entries: list[Evidence]) -> list[Evidence]:
    if len({item.kind for item in entries}) != len(entries):
        raise ValueError("Declare each evidence kind once.")
    return entries


Checklist = Annotated[
    list[Evidence],
    Field(max_length=len(EvidenceKind)),
    AfterValidator(distinct_evidence),
]


class VendorData(Model):
    vendor_name: Name
    service_category: Category
    business_criticality: Criticality
    sensitive_data_access: StrictBool
    requester_department: Department
    service_description: Description
    evidence: Checklist = Field(default_factory=list)


class CreateRequest(VendorData):
    expected_version: Literal[0] = 0


class Versioned(Model):
    expected_version: Version


class EditRequest(Versioned):
    vendor_name: Name | SkipJsonSchema[None] = None
    service_category: Category | SkipJsonSchema[None] = None
    business_criticality: Criticality | SkipJsonSchema[None] = None
    sensitive_data_access: StrictBool | SkipJsonSchema[None] = None
    requester_department: Department | SkipJsonSchema[None] = None
    service_description: Description | SkipJsonSchema[None] = None
    evidence: Checklist | SkipJsonSchema[None] = None

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        changes = self.model_fields_set - {"expected_version"}
        if not changes or any(getattr(self, field) is None for field in changes):
            raise ValueError("Supply at least one edit and omit unchanged fields.")
        return self


class Factor(Model):
    field: str
    reason: str
    points: int


class Risk(Model):
    score: int
    band: RiskBand
    factors: list[Factor]


class RequestView(VendorData):
    id: UUID
    status: Status
    version: int
    created_at: datetime
    updated_at: datetime
    required_evidence: list[EvidenceKind]
    missing_evidence: list[EvidenceKind]
    risk: Risk


class RequestList(Model):
    items: list[RequestView]
    counts: dict[Status, int]


class AuditView(Model):
    id: int
    request_id: UUID
    event_type: str
    actor_type: str
    from_status: Status | None
    to_status: Status
    detail: dict[str, object]
    created_at: datetime


class ConflictView(Model):
    detail: str
    current: RequestView
