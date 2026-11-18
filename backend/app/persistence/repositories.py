from collections import defaultdict
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, RowMapping, delete, func, insert, select, update

from app.domain import transitions
from app.domain.enums import Status
from app.domain.models import AuditView, Evidence, RequestList, RequestView, VendorData
from app.domain.rules import compute_risk, missing_evidence, required_evidence
from app.persistence.tables import audit_event, evidence, timestamp, vendor_request


class MissingRequest(Exception):
    pass


class Conflict(Exception):
    def __init__(self, message: str, current: RequestView) -> None:
        super().__init__(message)
        self.current = current


def view(row: RowMapping, entries: list[Evidence]) -> RequestView:
    fields = dict(row)
    data = VendorData.model_validate(
        {k: fields[k] for k in VendorData.model_fields if k != "evidence"}
        | {"evidence": entries}
    )
    return RequestView(
        **fields,
        evidence=entries,
        required_evidence=required_evidence(data),
        missing_evidence=missing_evidence(data),
        risk=compute_risk(data),
    )


def evidence_for(conn: Connection, ids: list[str]) -> dict[str, list[Evidence]]:
    grouped: dict[str, list[Evidence]] = defaultdict(list)
    if ids:
        rows = conn.execute(
            select(evidence)
            .where(evidence.c.request_id.in_(ids))
            .order_by(evidence.c.id)
        ).mappings()
        for r in rows:
            grouped[r["request_id"]].append(
                Evidence(kind=r["kind"], present=r["present"], pointer=r["pointer"])
            )
    return grouped


def get(conn: Connection, request_id: UUID) -> RequestView:
    key = str(request_id)
    row = (
        conn.execute(select(vendor_request).where(vendor_request.c.id == key))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise MissingRequest
    return view(row, evidence_for(conn, [key]).get(key, []))


def list_requests(conn: Connection, status: Status | None) -> RequestList:
    query = select(vendor_request).order_by(
        vendor_request.c.created_at.desc(), vendor_request.c.id
    )
    if status is not None:
        query = query.where(vendor_request.c.status == status)
    rows = conn.execute(query).mappings().all()
    entries = evidence_for(conn, [row["id"] for row in rows])
    counts = {s: 0 for s in Status}
    for state, count in conn.execute(
        select(vendor_request.c.status, func.count()).group_by(vendor_request.c.status)
    ):
        counts[Status(state)] = count
    return RequestList(
        items=[view(row, entries.get(row["id"], [])) for row in rows], counts=counts
    )


def replace_evidence(conn: Connection, key: UUID, entries: list[Evidence]) -> None:
    conn.execute(delete(evidence).where(evidence.c.request_id == str(key)))
    if entries:
        conn.execute(
            insert(evidence),
            [entry.model_dump() | {"request_id": str(key)} for entry in entries],
        )


def audit(
    conn: Connection,
    key: UUID,
    event: str,
    actor: str,
    before: Status | None,
    after: Status,
    detail: Mapping[str, object],
) -> None:
    conn.execute(
        insert(audit_event).values(
            request_id=str(key),
            event_type=event,
            actor_type=actor,
            from_status=before,
            to_status=after,
            detail=dict(detail),
        )
    )


def history(conn: Connection, key: UUID) -> list[AuditView]:
    get(conn, key)
    rows = conn.execute(
        select(audit_event)
        .where(audit_event.c.request_id == str(key))
        .order_by(audit_event.c.id)
    ).mappings()
    return [AuditView.model_validate(dict(row)) for row in rows]


def create(conn: Connection, key: UUID, data: VendorData) -> RequestView:
    status = transitions.apply(None, Status.DRAFT)
    conn.execute(
        insert(vendor_request).values(
            id=str(key),
            status=status,
            version=1,
            **data.model_dump(exclude={"evidence"}),
        )
    )
    replace_evidence(conn, key, data.evidence)
    audit(conn, key, "created", "requester", None, status, {"version": 1})
    return get(conn, key)


def check_version(current: RequestView, expected_version: int) -> None:
    if current.version != expected_version:
        raise Conflict("The request has changed. Reload its current version.", current)


def write(conn: Connection, current: RequestView, values: Mapping[str, Any]) -> None:
    result = conn.execute(
        update(vendor_request)
        .where(
            vendor_request.c.id == str(current.id),
            vendor_request.c.version == current.version,
        )
        .values(**values, version=current.version + 1, updated_at=timestamp())
    )
    if result.rowcount != 1:
        raise Conflict(
            "The request has changed. Reload its current version.",
            get(conn, current.id),
        )


def transition(
    conn: Connection,
    current: RequestView,
    target: Status,
    actor: str,
    detail: dict[str, object],
) -> RequestView:
    try:
        status = transitions.apply(current.status, target)
    except ValueError as exc:
        raise Conflict(str(exc), current) from exc
    write(conn, current, {"status": status})
    audit(
        conn,
        current.id,
        "status_changed",
        actor,
        current.status,
        status,
        detail | {"version": current.version + 1},
    )
    return get(conn, current.id)
