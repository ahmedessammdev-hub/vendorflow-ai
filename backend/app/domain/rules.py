from app.domain.enums import Category, Criticality, EvidenceKind, RiskBand
from app.domain.models import Factor, Risk, VendorData


def required_evidence(data: VendorData) -> list[EvidenceKind]:
    required = [EvidenceKind.REGISTRATION]
    if data.service_category in {Category.CLOUD, Category.SOFTWARE}:
        required.append(EvidenceKind.QUESTIONNAIRE)
    if data.business_criticality == Criticality.HIGH:
        required.append(EvidenceKind.SLA)
    return required


def missing_evidence(data: VendorData) -> list[EvidenceKind]:
    present = {entry.kind for entry in data.evidence if entry.present}
    return [kind for kind in required_evidence(data) if kind not in present]


def compute_risk(data: VendorData) -> Risk:
    criticality = data.business_criticality
    points = {Criticality.HIGH: 3, Criticality.MEDIUM: 1, Criticality.LOW: 0}
    factors = [
        Factor(
            field="business_criticality",
            reason=f"{criticality.value.capitalize()} criticality",
            points=points[criticality],
        )
    ]
    if data.sensitive_data_access:
        factors.append(
            Factor(
                field="sensitive_data_access", reason="Sensitive data access", points=2
            )
        )
    if data.service_category == Category.CLOUD:
        factors.append(
            Factor(field="service_category", reason="Cloud hosting", points=1)
        )
    score = sum(factor.points for factor in factors)
    band = (
        RiskBand.HIGH if score >= 4 else RiskBand.MEDIUM if score >= 2 else RiskBand.LOW
    )
    return Risk(score=score, band=band, factors=factors)
