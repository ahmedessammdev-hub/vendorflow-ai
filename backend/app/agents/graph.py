from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from app.agents.nodes import ReviewNodes, State


def human_review(state: State) -> State:
    decision = interrupt(
        {"request_id": state["request_id"], "review_version": state["version"] + 1}
    )
    return {"decision": decision}


def record_outcome(state: State) -> State:
    decision = state["decision"]
    if decision is None:
        raise RuntimeError("Missing persisted human decision.")
    return {"outcome": decision["action"]}


ReviewGraph = CompiledStateGraph[State, None, State, State]


def build_graph(nodes: ReviewNodes, saver: SqliteSaver) -> ReviewGraph:
    builder = StateGraph(State)
    builder.add_sequence(
        [
            nodes.load_context,
            nodes.intake_summary,
            nodes.compute_risk,
            nodes.recommendation,
            nodes.persist_assessment,
            human_review,
            record_outcome,
        ]
    )
    builder.add_edge(START, "load_context")
    builder.add_edge("record_outcome", END)
    return builder.compile(checkpointer=saver)
