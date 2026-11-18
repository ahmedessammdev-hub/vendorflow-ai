import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Protocol
from uuid import UUID

import httpx

from app.core.config import Settings
from app.domain.models import RequestView
from app.integration.adf import description


@dataclass(frozen=True)
class Issue:
    key: str
    id: str


class DeliveryError(Exception):
    """A safe fixed message and knowledge of whether another create is safe."""

    def __init__(
        self, message: str, *, uncertain: bool = False, retry_after: float | None = None
    ) -> None:
        super().__init__(message)
        self.uncertain = uncertain
        self.retry_after = retry_after


class JiraClient(Protocol):
    @property
    def site(self) -> str | None: ...

    def create(self, request: RequestView) -> Issue: ...
    def search(self, key: UUID) -> Issue | None: ...


def retry_delay(value: str) -> float:
    if value.isascii() and value.isdigit():
        seconds = value.lstrip("0") or "0"
        return float(seconds) if len(seconds) <= 10 else 99_999_999_999.0
    try:
        return max(
            0.0, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        )
    except (ValueError, TypeError, OverflowError):
        return 2.0


class LiveJira:
    def __init__(self, settings: Settings) -> None:
        self.site = settings.jira_base_url.rstrip("/")
        self.project = settings.jira_project_key
        self.issue_type = settings.jira_issue_type
        self.type_id: str | None = None
        self.ready = bool(
            self.site
            and self.project
            and settings.jira_email.strip()
            and settings.jira_api_token
            and settings.jira_api_token.get_secret_value().strip()
            and self.issue_type
        )
        self.http = httpx.Client(
            base_url=self.site or "https://unconfigured.invalid",
            auth=(
                settings.jira_email,
                settings.jira_api_token.get_secret_value()
                if settings.jira_api_token
                else "",
            ),
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=False,
        )

    def call(
        self, method: str, path: str, *, creating: bool = False, **kwargs: Any
    ) -> dict[str, Any]:
        if not self.ready:
            raise DeliveryError(
                "Configure the Jira site, project, issue type and credentials."
            )
        try:
            response = self.http.request(method, path, **kwargs)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
            raise DeliveryError("Could not connect to Jira.", retry_after=1.0) from None
        except httpx.RequestError:
            raise DeliveryError(
                "Jira response was interrupted.", uncertain=creating
            ) from None
        code = response.status_code
        if code == 429:
            raise DeliveryError(
                "Jira rate limit reached.",
                retry_after=retry_delay(response.headers.get("Retry-After", "")),
            )
        if code != (201 if creating else 200):
            raise DeliveryError(
                f"Jira returned HTTP {code}.",
                uncertain=creating and code not in {400, 401, 403, 404, 422},
            )
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError
            return data
        except ValueError:
            raise DeliveryError(
                "Jira returned an unreadable response.", uncertain=creating
            ) from None

    def resolve_type(self) -> str:
        start = 0
        while True:
            data = self.call(
                "GET",
                f"/rest/api/3/issue/createmeta/{self.project}/issuetypes",
                params={"startAt": start, "maxResults": 50},
            )
            kinds = data.get("issueTypes", data.get("values"))
            total = data.get("total")
            if (
                not isinstance(kinds, list)
                or total is not None
                and (type(total) is not int or total < 0)
                or data.get("startAt", start) != start
            ):
                raise DeliveryError("Invalid Jira create metadata.")
            for item in kinds:
                if (
                    isinstance(item, dict)
                    and item.get("name") == self.issue_type
                    and str(item.get("id", "")).isdigit()
                ):
                    return str(item["id"])
            start += len(kinds)
            if (
                not kinds
                or (total is not None and start >= total)
                or (total is None and data.get("isLast") is not False)
                or data.get("isLast") is True
            ):
                raise DeliveryError(
                    "Issue type unavailable in the configured Jira project."
                )

    @staticmethod
    def issue(data: dict[str, Any]) -> Issue:
        key = data.get("key")
        external_id = data.get("id")
        if (
            not isinstance(key, str)
            or not re.fullmatch(r"[A-Z][A-Z0-9_]*-[1-9][0-9]*", key)
            or not isinstance(external_id, str)
            or not external_id.isascii()
            or not external_id.isdigit()
        ):
            raise DeliveryError(
                "Jira issue identity could not be verified.", uncertain=True
            )
        return Issue(key, external_id)

    def create(self, request: RequestView) -> Issue:
        if self.type_id is None:
            self.type_id = self.resolve_type()
        fields = {
            "project": {"key": self.project},
            "issuetype": {"id": self.type_id},
            "summary": f"Supplier onboarding: {request.vendor_name}",
            "description": description(request),
            "labels": [f"vf-{request.id}"],
        }
        return self.issue(
            self.call(
                "POST", "/rest/api/3/issue", creating=True, json={"fields": fields}
            )
        )

    def search(self, key: UUID) -> Issue | None:
        marker = f"vf-{key}"
        data = self.call(
            "POST",
            "/rest/api/3/search/jql",
            json={"jql": f'labels = "{marker}"', "fields": ["labels"], "maxResults": 2},
        )
        items = data.get("issues")
        if (
            not isinstance(items, list)
            or data.get("nextPageToken")
            or data.get("isLast") is False
            or len(items) > 1
        ):
            raise DeliveryError("Jira marker search was inconclusive.", uncertain=True)
        if not items:
            return None
        item = items[0]
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("fields"), dict)
            or not isinstance(item["fields"].get("labels"), list)
            or marker not in item["fields"]["labels"]
        ):
            raise DeliveryError("Jira marker could not be verified.", uncertain=True)
        return self.issue(item)
