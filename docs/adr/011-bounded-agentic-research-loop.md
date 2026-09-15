# ADR-011: Bounded agentic research loop

## Status

Accepted — 2026-09-15

## Context

Some research questions require more than one predetermined operation: the
system may need to discover available KnowledgeBases, select an authorized
scope, run document search, inspect the result, and decide whether another
search is useful. A fixed chain cannot make that choice, while an unrestricted
agent loop risks runaway provider cost, unauthorized scope selection, and
unverifiable answers.

## Decision

Add a model-directed loop with two read-only tools:

- `list_knowledge_bases`
- `search_documents`

Use `tool_choice="auto"` while budget remains so the model can choose a tool or
finish. Disable parallel calls and allow at most one tool per turn and three
tool calls per run. After the third call, set `tool_choice="none"` to force a
final answer and return `tool_budget_reached` as the stop reason.

The server injects `workspace_id`. Model-selected KnowledgeBase IDs pass through
the existing workspace scope resolver before search. Every search result gets a
stable chunk-derived citation ID; the final structured response may cite only
IDs actually observed during the run. Return ordered tool-step summaries,
stop reason, and full citation provenance to the client.

## Consequences

- The model controls the next useful read operation, but never identity,
  authorization, tool registration, parallelism, or execution budget.
- A run makes at most four model requests: up to three tool decisions and one
  forced final synthesis.
- Repeated searches can compare evidence across KnowledgeBases.
- Unknown tools, malformed arguments, foreign scope IDs, parallel calls,
  fabricated citations, and empty answers fail closed.
- Runs are currently synchronous and not persisted; resumable long-running
  research is deferred until its user need justifies durable run state.
