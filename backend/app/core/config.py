import re
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )
    database_path: Path = REPO_ROOT / "vendorflow.sqlite"
    llm_api_key: SecretStr | None = None
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = Field(default=30, gt=0, le=300)
    llm_reasoning_effort: Literal["", "low", "medium", "high"] = ""
    llm_max_tokens: int | None = Field(default=None, ge=128, le=16384)
    llm_input_usd_per_million: float | None = Field(default=None, ge=0)
    llm_output_usd_per_million: float | None = Field(default=None, ge=0)
    jira_mode: Literal["simulation", "live"] = "simulation"

    jira_base_url: str = ""
    jira_project_key: str = Field(default="", pattern=r"^(?:[A-Z][A-Z0-9_]{0,39})?$")
    jira_issue_type: str = "Task"
    jira_email: str = ""
    jira_api_token: SecretStr | None = None

    @field_validator("jira_base_url")
    @classmethod
    def jira_site(cls, value: str) -> str:
        site = value.removesuffix("/").lower()
        if site and not re.fullmatch(
            r"https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.atlassian\.net", site
        ):
            raise ValueError("Use the HTTPS origin of your Atlassian Cloud site.")
        return site

    @property
    def checkpoint_path(self) -> Path:
        if self.database_path.name == "vendorflow.sqlite":
            return self.database_path.with_name("checkpoints.sqlite")
        return self.database_path.with_suffix(".checkpoints.sqlite")

    @property
    def llm_configured(self) -> bool:
        return bool(
            self.llm_api_key
            and self.llm_api_key.get_secret_value().strip()
            and self.llm_base_url.strip()
            and self.llm_model.strip()
        )
