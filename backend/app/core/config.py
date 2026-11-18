from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )
    llm_api_key: SecretStr | None = None
    llm_base_url: str = ""
    llm_model: str = ""
    jira_mode: Literal["simulation", "live"] = "simulation"

    @property
    def llm_configured(self) -> bool:
        return bool(
            self.llm_api_key
            and self.llm_api_key.get_secret_value().strip()
            and self.llm_base_url.strip()
            and self.llm_model.strip()
        )
