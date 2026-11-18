from app.domain.enums import Status

_ALLOWED: dict[Status | None, set[Status]] = {
    None: {Status.DRAFT},
    Status.DRAFT: {Status.SUBMITTED},
    Status.NEEDS_CHANGES: {Status.SUBMITTED},
    Status.SUBMITTED: {Status.NEEDS_CHANGES, Status.UNDER_REVIEW},
    Status.UNDER_REVIEW: {Status.AWAITING_APPROVAL},
    Status.AWAITING_APPROVAL: {Status.APPROVED, Status.REJECTED, Status.NEEDS_CHANGES},
    Status.APPROVED: {Status.JIRA_PENDING},
    Status.JIRA_PENDING: {Status.JIRA_CREATED, Status.JIRA_FAILED},
    Status.JIRA_FAILED: {Status.JIRA_PENDING},
}


def apply(current: Status | None, target: Status) -> Status:
    if target not in _ALLOWED.get(current, set()):
        raise ValueError(f"Invalid request transition from {current} to {target}.")
    return target
