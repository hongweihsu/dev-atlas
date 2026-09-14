# ADR-009: Product conversations with LangGraph orchestration

## Status

Accepted — 2026-09-14

## Context

Phase 12 needs multi-turn questions that survive reloads, remain inspectable, and
cannot cross workspace or user boundaries. LangGraph offers checkpoint-backed
workflow state, but a checkpoint thread identifier alone is not a DevAtlas
authorization model. The product also needs stable conversation lists and exact
historical citation snapshots.

## Decision

Store conversation metadata and immutable turns in DevAtlas-owned PostgreSQL
tables. Every repository operation requires `workspace_id` and `user_id`; an
unknown or foreign conversation is reported as not found.

Use a LangGraph `StateGraph` to make the turn workflow explicit:

```text
load_history -> contextualize -> answer -> persist
```

Only the six most recent turns are supplied for contextualization. The first
turn skips rewriting. Follow-up rewriting must produce a standalone question,
preserve exact identifiers, and never answer the question. Retrieval and answer
generation retain the existing authorized KnowledgeBase scope and citation
validation.

## Consequences

- Conversation history is queryable and auditable without decoding framework
  checkpoints.
- Product authorization remains in SQL queries, not in an LLM prompt or an
  unchecked LangGraph `thread_id`.
- The contextualization window and provider cost are bounded.
- Historical citations remain explainable if a document's active version changes.
- A follow-up turn adds one model request for query rewriting.
- LangGraph checkpointing is deferred until resumable tool or agent execution
  needs it. Conversation rows are not workflow checkpoints.
