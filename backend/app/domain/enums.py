from enum import StrEnum


class Status(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    NEEDS_CHANGES = "NEEDS_CHANGES"
    UNDER_REVIEW = "UNDER_REVIEW"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    JIRA_PENDING = "JIRA_PENDING"
    JIRA_CREATED = "JIRA_CREATED"
    JIRA_FAILED = "JIRA_FAILED"


class Category(StrEnum):
    CLOUD = "cloud_hosting"
    SOFTWARE = "software"
    CONSULTING = "consulting"


class Criticality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceKind(StrEnum):
    REGISTRATION = "business_registration"
    QUESTIONNAIRE = "security_questionnaire"
    SLA = "service_sla"


class RiskBand(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
