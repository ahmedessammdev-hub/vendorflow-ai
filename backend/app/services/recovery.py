from threading import Lock
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langsmith import tracing_context
from sqlalchemy import Engine, select

from app.agents.graph import ReviewGraph
from app.agents.nodes import State
from app.domain.enums import Status
from app.persistence import repositories as repo
from app.persistence.database import write_transaction
from app.persistence.tables import review_decision, vendor_request


class ReviewWorkflow:
    """Serialise checkpoint operations per thread in the local, single-worker demo."""

    def __init__(self, engine: Engine, graph: ReviewGraph) -> None:
        self.engine = engine
        self.graph = graph
        self.locks = [Lock() for _ in range(64)]

    def recover(self) -> None:
        active = select(vendor_request.c.id).where(
            vendor_request.c.status.in_([Status.UNDER_REVIEW, Status.AWAITING_APPROVAL])
        )
        with self.engine.begin() as conn:
            keys = conn.scalars(
                active.union(select(review_decision.c.request_id))
            ).all()
        for key in keys:
            self.drive(UUID(key))

    def drive(self, key: UUID) -> None:
        with self.locks[key.int % len(self.locks)], tracing_context(enabled=False):
            config: RunnableConfig = {"configurable": {"thread_id": str(key)}}
            snapshot = self.graph.get_state(config)
            # Finish the previous submission before reusing the UUID after request_changes.
            if snapshot.values and snapshot.next:
                version = snapshot.values.get("version")
                with self.engine.begin() as conn:
                    decision = (
                        conn.execute(
                            select(review_decision).filter_by(
                                request_id=str(key), request_version=version + 1
                            )
                        )
                        .mappings()
                        .one_or_none()
                        if version is not None
                        else None
                    )
                if decision is not None:
                    payload = {
                        k: decision[k]
                        for k in (
                            "action",
                            "reviewer_label",
                            "reason",
                            "request_version",
                        )
                    }
                    self.graph.invoke(
                        Command(resume=payload) if snapshot.interrupts else None,
                        config,
                        durability="sync",
                    )
                    snapshot = self.graph.get_state(config)
            with self.engine.begin() as conn:
                request = repo.get(conn, key)
            if request.status != Status.UNDER_REVIEW:
                return
            if snapshot.values.get("version") != request.version:
                initial: State = {"request_id": str(key), "version": request.version}
                self.graph.invoke(initial, config, durability="sync")
            elif not snapshot.interrupts:
                self.graph.invoke(None, config, durability="sync")
            paused = self.graph.get_state(config)
            if not paused.interrupts or paused.values["version"] != request.version:
                raise RuntimeError("Expected a durable human review interrupt.")
            with write_transaction(self.engine) as conn:
                current = repo.get(conn, key)
                if (
                    current.status == Status.UNDER_REVIEW
                    and current.version == request.version
                ):
                    repo.transition(
                        conn,
                        current,
                        Status.AWAITING_APPROVAL,
                        "system",
                        {"assessment_version": request.version},
                    )
