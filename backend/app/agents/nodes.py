from time import perf_counter
from typing import Any, TypedDict
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import Engine, insert, select, update

from app.agents.llm_adapter import Provider, ProviderDown, SchemaUnsupported
from app.agents.prompts import PROMPT_VERSION, messages
from app.agents.schemas import IntakeSummary, Recommendation
from app.domain.models import VendorData
from app.domain.rules import compute_risk
from app.persistence import repositories as repo
from app.persistence.database import write_transaction
from app.persistence.tables import assessment, llm_call


class CitationMismatch(ValueError):
    pass


class BlockedOutput(ValueError):
    pass


class Stage(TypedDict):
    outcome: str
    output: dict[str, Any] | None


class State(TypedDict, total=False):
    request_id: str
    version: int
    facts: dict[str, Any]
    risk: dict[str, Any]
    summary: Stage
    recommendation: Stage
    decision: dict[str, Any] | None
    outcome: str | None


def check_citations(advice: Recommendation, facts: dict[str, Any]) -> None:
    fields = advice.cited_input_fields
    if (
        len(fields) != len(set(fields))
        or set(fields) != {c.field for c in advice.citations}
        or len(fields) != len(advice.citations)
    ):
        raise CitationMismatch("Citations must match cited fields.")
    for citation in advice.citations:
        original = facts.get(citation.field)
        if type(original) is not type(citation.value) or original != citation.value:
            raise CitationMismatch("Citation does not match a request fact.")


class ReviewNodes:
    def __init__(
        self, engine: Engine, provider: Provider | None, secret: str | None
    ) -> None:
        self.engine = engine
        self.provider = provider
        self.secret = secret

    def load_context(self, state: State) -> State:
        with self.engine.begin() as conn:
            request = repo.get(conn, UUID(state["request_id"]))
        if request.version != state["version"]:
            raise RuntimeError("Review input version changed.")
        return {
            "facts": request.model_dump(
                mode="json", include=set(VendorData.model_fields)
            ),
            "decision": None,
            "outcome": None,
        }

    def compute_risk(self, state: State) -> State:
        data = VendorData.model_validate(state["facts"])
        return {"risk": compute_risk(data).model_dump(mode="json")}

    def attempt(
        self,
        state: State,
        node: str,
        schema: type[BaseModel],
        number: int,
        json_mode: bool,
        repair: bool,
        payload: dict[str, Any],
    ) -> Stage:
        provider = self.provider
        ident = dict(
            request_id=state["request_id"],
            request_version=state["version"],
            node=node,
            attempt=number,
        )
        with write_transaction(self.engine) as conn:
            row = (
                conn.execute(select(llm_call).filter_by(**ident))
                .mappings()
                .one_or_none()
            )
            if row is not None:
                if row["outcome"] == "STARTED":
                    # The process stopped between sending and recording the response.
                    conn.execute(
                        update(llm_call)
                        .where(llm_call.c.id == row["id"])
                        .values(outcome="UNAVAILABLE", failure_reason="interrupted")
                    )
                    return {"outcome": "UNAVAILABLE", "output": None}
                return {"outcome": row["outcome"], "output": row["validated_output"]}
            if provider is None:
                return {"outcome": "UNAVAILABLE", "output": None}
            conn.execute(
                insert(llm_call).values(
                    **ident,
                    model=provider.model,
                    prompt_version=PROMPT_VERSION,
                    latency_ms=None,
                    outcome="STARTED",
                )
            )
        started = perf_counter()
        tokens_in = tokens_out = None
        model = provider.model
        parsed = None
        status = "OK"
        failure_reason = None
        try:
            system, user = messages(schema, payload, repair)
            reply = provider.complete(schema, system, user, json_mode)
            if reply.model and not (self.secret and self.secret in reply.model):
                model = reply.model
            tokens_in, tokens_out = reply.tokens_in, reply.tokens_out
            value = schema.model_validate_json(reply.content, strict=True)
            if self.secret and self.secret in value.model_dump_json():
                raise BlockedOutput
            if isinstance(value, Recommendation):
                check_citations(value, state["facts"])
            parsed = value.model_dump(mode="json")
        except SchemaUnsupported:
            failure_reason = "schema_format_unsupported"
            status = "FORMAT_UNSUPPORTED"
        except ProviderDown as exc:
            failure_reason = exc.category
            status = "UNAVAILABLE"
        except ValidationError as exc:
            failure_reason = (
                "invalid_json"
                if any(
                    e["type"] == "json_invalid" for e in exc.errors(include_input=False)
                )
                else "schema_validation"
            )
            status = "INVALID_OUTPUT"
        except CitationMismatch:
            failure_reason = "citation_mismatch"
            status = "INVALID_OUTPUT"
        except BlockedOutput:
            failure_reason = "blocked_output"
            status = "INVALID_OUTPUT"
        except ValueError:
            failure_reason = "output_validation"
            status = "INVALID_OUTPUT"
        with write_transaction(self.engine) as conn:
            conn.execute(
                update(llm_call)
                .filter_by(**ident)
                .values(
                    outcome=status,
                    failure_reason=failure_reason,
                    validated_output=parsed,
                    model=model,
                    latency_ms=round((perf_counter() - started) * 1000),
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                )
            )
        return {"outcome": status, "output": parsed}

    def stage(
        self, state: State, node: str, schema: type[BaseModel], payload: dict[str, Any]
    ) -> Stage:
        json_mode = repair = False
        for attempt in range(1, 4):
            result = self.attempt(
                state, node, schema, attempt, json_mode, repair, payload
            )
            if result["outcome"] == "FORMAT_UNSUPPORTED" and not json_mode:
                json_mode = True
            elif result["outcome"] == "INVALID_OUTPUT" and not repair:
                repair = True
            else:
                return result
        return {"outcome": "INVALID_OUTPUT", "output": None}

    def intake_summary(self, state: State) -> State:
        return {
            "summary": self.stage(
                state, "intake_summary", IntakeSummary, {"request": state["facts"]}
            )
        }

    def recommendation(self, state: State) -> State:
        payload = {
            "request": state["facts"],
            "risk": state["risk"],
            "summary": state["summary"]["output"],
        }
        return {
            "recommendation": self.stage(
                state, "recommendation", Recommendation, payload
            )
        }

    def persist_assessment(self, state: State) -> State:
        summary, advice = state["summary"], state["recommendation"]
        outcomes = {summary["outcome"], advice["outcome"]}
        status = (
            "INVALID_OUTPUT"
            if "INVALID_OUTPUT" in outcomes
            else "UNAVAILABLE"
            if outcomes != {"OK"}
            else "OK"
        )
        with write_transaction(self.engine) as conn:
            model = conn.scalar(
                select(llm_call.c.model)
                .filter_by(
                    request_id=state["request_id"], request_version=state["version"]
                )
                .order_by(llm_call.c.id.desc())
                .limit(1)
            )
            result = conn.execute(
                update(assessment)
                .filter_by(
                    request_id=state["request_id"], request_version=state["version"]
                )
                .values(
                    summary=summary["output"],
                    recommendation=advice["output"],
                    ai_status=status,
                    model=model,
                    prompt_version=PROMPT_VERSION,
                )
            )
            if result.rowcount != 1:
                raise RuntimeError("Review assessment is missing.")
        return {}
