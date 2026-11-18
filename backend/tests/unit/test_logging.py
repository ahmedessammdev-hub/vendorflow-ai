from pydantic import SecretStr

from app.core.config import Settings
from app.core.logging import redactor


def test_vf10_nested_secrets_and_values_redacted() -> None:
    processor = redactor(Settings(llm_api_key=SecretStr("synthetic-redaction-canary")))
    event = processor(
        None,
        "info",
        {
            "nested": [
                {
                    "Authorization": "Bearer example",
                    "note": "prefix synthetic-redaction-canary",
                }
            ],
            "password": "anything",
        },
    )
    assert event == {
        "nested": [{"Authorization": "[REDACTED]", "note": "prefix [REDACTED]"}],
        "password": "[REDACTED]",
    }
