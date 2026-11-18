import itertools

import pytest

from app.domain.enums import Category, Criticality, EvidenceKind, RiskBand, Status
from app.domain.models import Evidence, VendorData
from app.domain.rules import compute_risk, missing_evidence, required_evidence
from app.domain.transitions import apply


def vendor(category: Category, criticality: Criticality, sensitive: bool) -> VendorData:
    return VendorData(
        vendor_name="Test Supplier",
        service_category=category,
        business_criticality=criticality,
        sensitive_data_access=sensitive,
        requester_department="Testing",
        service_description="Synthetic service.",
    )


@pytest.mark.parametrize(
    ("category", "criticality", "sensitive"),
    list(itertools.product(Category, Criticality, (False, True))),
)
def test_vf03_score_and_vf02_checklist(
    category: Category, criticality: Criticality, sensitive: bool
) -> None:
    request = vendor(category, criticality, sensitive)
    points = {Criticality.LOW: 0, Criticality.MEDIUM: 1, Criticality.HIGH: 3}[
        criticality
    ]
    expected = points + 2 * int(sensitive) + int(category == Category.CLOUD)
    risk = compute_risk(request)
    assert risk.score == expected == sum(f.points for f in risk.factors)
    assert (
        risk.band
        == [
            RiskBand.LOW,
            RiskBand.LOW,
            RiskBand.MEDIUM,
            RiskBand.MEDIUM,
            RiskBand.HIGH,
            RiskBand.HIGH,
            RiskBand.HIGH,
        ][expected]
    )
    needs = [EvidenceKind.REGISTRATION]
    if category != Category.CONSULTING:
        needs.append(EvidenceKind.QUESTIONNAIRE)
    if criticality == Criticality.HIGH:
        needs.append(EvidenceKind.SLA)
    assert required_evidence(request) == needs == missing_evidence(request)
    request.evidence = [Evidence(kind=k, present=True) for k in needs]
    assert not missing_evidence(request)
    assert compute_risk(request) == risk


LEGAL = {
    (None, "DRAFT"),
    ("DRAFT", "SUBMITTED"),
    ("NEEDS_CHANGES", "SUBMITTED"),
    ("SUBMITTED", "NEEDS_CHANGES"),
    ("SUBMITTED", "UNDER_REVIEW"),
    ("UNDER_REVIEW", "AWAITING_APPROVAL"),
    ("AWAITING_APPROVAL", "APPROVED"),
    ("AWAITING_APPROVAL", "REJECTED"),
    ("AWAITING_APPROVAL", "NEEDS_CHANGES"),
    ("APPROVED", "JIRA_PENDING"),
    ("JIRA_PENDING", "JIRA_CREATED"),
    ("JIRA_PENDING", "JIRA_FAILED"),
    ("JIRA_FAILED", "JIRA_PENDING"),
}


@pytest.mark.parametrize(
    ("before", "after"), list(itertools.product([None, *Status], Status))
)
def test_transition_matrix(before: Status | None, after: Status) -> None:
    if (before, after) in LEGAL:
        assert apply(before, after) == after
    else:
        with pytest.raises(ValueError, match="Invalid request transition"):
            apply(before, after)
