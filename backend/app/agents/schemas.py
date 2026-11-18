from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictStr, StringConstraints

from app.domain.models import Model, RequestView, Versioned

Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]
AIStatus = Literal["OK", "UNAVAILABLE", "INVALID_OUTPUT"]
Action = Literal["approve", "reject", "request_changes"]


class IntakeSummary(Model):
    what_is_requested: Text
    service_description: Text
    evidence_summary: Text
    missing_information: list[Text]


class Citation(Model):
    field: Text
    value: StrictStr | StrictBool


class Recommendation(Model):
    recommendation: Literal["approve_review", "request_more_info", "escalate"]
    justification: Text
    cited_input_fields: Annotated[list[Text], Field(min_length=1)]
    citations: Annotated[list[Citation], Field(min_length=1)]
    caution: Text


class AssessmentView(Model):
    request_version: int
    ai_status: AIStatus
    model: str | None
    prompt_version: str
    summary: IntakeSummary | None
    recommendation: Recommendation | None


class RequestDetail(RequestView):
    assessment: AssessmentView | None = None


class HumanDecision(Versioned):
    action: Action
    reviewer_label: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]
    reason: Text
