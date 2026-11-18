from dataclasses import dataclass
from typing import Protocol

from openai import APIError, APIResponseValidationError, BadRequestError, OpenAI
from openai.types.chat.completion_create_params import ResponseFormat
from pydantic import BaseModel

from app.core.config import Settings


@dataclass(frozen=True)
class Reply:
    content: str
    tokens_in: int | None
    tokens_out: int | None
    model: str | None = None


class ProviderDown(Exception):
    pass


class SchemaUnsupported(Exception):
    pass


class Provider(Protocol):
    @property
    def model(self) -> str: ...
    def complete(
        self, schema: type[BaseModel], system: str, data: str, json_mode: bool
    ) -> Reply: ...


class CompatibleProvider:
    def __init__(self, config: Settings) -> None:
        if config.llm_api_key is None:
            raise ValueError("Missing LLM configuration.")
        self.model = config.llm_model
        self.client = OpenAI(
            api_key=config.llm_api_key.get_secret_value(),
            base_url=config.llm_base_url,
            timeout=30.0,
            max_retries=0,
            _strict_response_validation=True,
        )

    def complete(
        self, schema: type[BaseModel], system: str, data: str, json_mode: bool
    ) -> Reply:
        response_format: ResponseFormat
        if json_mode:
            response_format = {"type": "json_object"}
        else:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": schema.model_json_schema(),
                },
            }
        try:
            result = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": data},
                ],
                response_format=response_format,
            )
        except BadRequestError as exc:
            if not json_mode and any(
                word in str(exc).lower()
                for word in ("response_format", "json_schema", "json schema")
            ):
                raise SchemaUnsupported from None
            raise ProviderDown from None
        except APIResponseValidationError:
            return Reply("", None, None)
        except APIError:
            raise ProviderDown from None
        if not result.choices:
            return Reply("", None, None)
        usage = result.usage
        return Reply(
            result.choices[0].message.content or "",
            usage.prompt_tokens if usage else None,
            usage.completion_tokens if usage else None,
            result.model,
        )
