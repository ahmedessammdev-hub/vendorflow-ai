from typing import Any

from app.domain.models import RequestView


def description(request: RequestView) -> dict[str, Any]:
    lines = [
        f"VendorFlow Request ID: {request.id}",
        f"Supplier: {request.vendor_name}",
        f"Department: {request.requester_department}",
        request.service_description,
        f"Illustrative risk: {request.risk.score} ({request.risk.band.value})",
    ]
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": line}]}
            for line in lines
        ],
    }
