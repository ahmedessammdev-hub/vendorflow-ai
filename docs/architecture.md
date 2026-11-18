# Architecture

## One-sentence design

The LLM writes advice, a deterministic state machine and a human decide, and every external write goes through an outbox that can prove it ran at most once.

## Components

```mermaid
flowchart LR
  subgraph Browser
    UI[Angular app<br/>dashboard · form · detail · review queue]
  end
  subgraph Backend[FastAPI on 127.0.0.1:8000]
    API[api/] --> SVC[services/]
    SVC --> DOM[domain/<br/>rules · transitions]
    SVC --> REPO[persistence/]
    SVC --> GRAPH[agents/ LangGraph]
    SVC --> DISP[integration/ dispatcher]
    GRAPH --> LLMA[llm_adapter]
    DISP --> JC[JiraClient interface]
  end
  REPO --> DB[(vendorflow.sqlite)]
  GRAPH --> CP[(checkpoints.sqlite)]
  LLMA -.-> LLM[OpenAI-compatible LLM]
  JC -.-> SIM[Simulation client]
  JC -.-> JIRA[Jira Cloud REST v3]
  UI -->|REST + generated types| API
```

Dependencies point inward. `domain/` knows nothing about the web, the database, the LLM or Jira, so its rules can be tested as plain functions.

## Request state machine

```mermaid
stateDiagram-v2
  [*] --> DRAFT
  DRAFT --> SUBMITTED: submit
  SUBMITTED --> NEEDS_CHANGES: evidence missing
  SUBMITTED --> UNDER_REVIEW: complete
  NEEDS_CHANGES --> SUBMITTED: resubmit
  UNDER_REVIEW --> AWAITING_APPROVAL: graph paused at interrupt
  AWAITING_APPROVAL --> APPROVED: human approve
  AWAITING_APPROVAL --> REJECTED: human reject
  AWAITING_APPROVAL --> NEEDS_CHANGES: human request changes
  APPROVED --> JIRA_PENDING: outbox row exists
  JIRA_PENDING --> JIRA_CREATED: 201 or found by marker
  JIRA_PENDING --> JIRA_FAILED: definite failure or uncertain
  JIRA_FAILED --> JIRA_PENDING: reconcile / safe retry
  REJECTED --> [*]
  JIRA_CREATED --> [*]
```

Only `domain/transitions.py` holds this table. Every other layer asks it.

## Review graph

```mermaid
flowchart TD
  S([start]) --> A[load_context<br/>deterministic]
  A --> B[intake_summary<br/>LLM → IntakeSummary]
  B --> C[compute_risk<br/>deterministic]
  C --> D[recommendation<br/>LLM → Recommendation]
  D --> E[persist_assessment<br/>idempotent upsert]
  E --> F{{human_review<br/>interrupt}}
  F -->|Command resume| G[record_outcome<br/>idempotent]
  G --> Z([end])
```

- `thread_id` is the request UUID.
- Nodes return partial state updates; LangGraph checkpoints after each node, so a restart continues from the last finished node and does not repeat a paid LLM call.
- `human_review` contains only the `interrupt()` call. A node restarts from its first line on resume, so nothing with side effects may sit before the interrupt.
- An LLM failure does not fail the graph. The node returns `ai_status` and the flow continues to the human.
- The graph has no Jira node.

## Decision and Jira outbox

```mermaid
sequenceDiagram
  participant R as Reviewer
  participant API as Decision endpoint
  participant DB as vendorflow.sqlite
  participant G as LangGraph
  participant D as Dispatcher
  participant J as Jira (live or sim)

  R->>API: approve + reason + expected_version
  API->>DB: BEGIN IMMEDIATE
  API->>DB: check version and status
  API->>DB: insert ReviewDecision, JiraOperation(PENDING), AuditEvent, set status
  API->>DB: COMMIT
  API->>G: Command(resume=decision)
  API-->>R: 200 current state
  API->>D: trigger
  D->>DB: claim PENDING → IN_FLIGHT
  D->>J: create issue with label vf-<uuid>
  alt 201
    D->>DB: CREATED + key
  else definite failure
    D->>DB: FAILED + sanitized error
  else timeout / 5xx
    D->>DB: UNCERTAIN
    D->>J: search by label, with backoff
    J-->>D: found?
    D->>DB: CREATED, or stay UNCERTAIN
  end
```

Three independent guards stop a duplicate issue: the version check on the request, the UNIQUE constraint on `JiraOperation.request_id`, and the claim step in the dispatcher. Honest limit: Jira offers no idempotency key on create, and its search index is eventually consistent, so after an ambiguous failure the system cannot always know the truth by itself. In that case it stops and asks a human rather than guessing.

## Data model

| Table | Key columns | Constraints |
|---|---|---|
| `vendor_request` | id (UUID), vendor fields, status, version, timestamps | status CHECK; version increments on every write |
| `evidence` | request_id, kind, present, pointer | UNIQUE(request_id, kind); kind CHECK |
| `assessment` | request_id, score, band, factors, summary, recommendation, ai_status, model, prompt_version | UNIQUE(request_id, request_version) |
| `review_decision` | request_id, request_version, reviewer_label, action, reason | UNIQUE(request_id, request_version) |
| `jira_operation` | request_id, mode, status, issue_key, marker, attempts, last_error, last_checked_at | **UNIQUE(request_id)** |
| `audit_event` | request_id, actor_type, event_type, from_status, to_status, detail, created_at | insert-only in code |
| `llm_call` | request_id, node, model, prompt_version, latency_ms, tokens_in, tokens_out, outcome | — |

## Failure handling at a glance

| Failure | Behavior |
|---|---|
| LLM key missing or provider down | `ai_status = UNAVAILABLE`; request still reaches the human; UI says so |
| LLM returns bad JSON or fake field names | one repair try, then `INVALID_OUTPUT`; never auto-approves |
| Process dies during the graph | startup recovery re-invokes; checkpointer skips finished nodes |
| Process dies after decision commit, before resume | recovery resumes the thread from the stored decision |
| Process dies while calling Jira | operation becomes `UNCERTAIN`; reconcile by label |
| Double click or concurrent approve | one decision, one operation; others get the stored result or 409 |
| Stale browser tab | 409 with the current state; UI reloads |

## Architecture decision records

| ADR | Decision | Trade-off accepted |
|---|---|---|
| 001 | Human approval gates every external write | Slower than automation; that is the point |
| 002 | Jira via outbox + label reconciliation, outside the graph | More code than one API call; gives a defensible duplicate story |
| 003 | LLM as two schema-bound nodes, no tool calling | Less "agentic"; far more testable and cheaper |
| 004 | SQLite in WAL mode, two files | Single machine only; fine for a demo |

## Path to production (documented, not built)

Postgres with the LangGraph Postgres checkpointer; outbox drained by a queue worker; OIDC login with role-based access and reviewer ≠ requester enforcement; audit log in append-only storage; secrets in a vault; Jira through OAuth 2.0 (3LO) or a Forge app instead of a personal API token; OpenTelemetry traces; an evaluation set reviewed by procurement experts before any real use of the risk rubric.
