# ADR-010: Server-authorized bounded tool calling

## Status

Accepted — 2026-09-15

## Context

Document RAG cannot reliably answer questions about live application metadata,
such as which KnowledgeBase currently contains the most documents. Giving a
model unrestricted application or database access would bypass Retrieval Works's
workspace authorization boundary and could create unbounded execution loops.

## Decision

Introduce one read-only `list_knowledge_bases` function tool through the OpenAI
Responses API. Its strict JSON schema accepts no caller-controlled arguments.
The API authenticates the request and injects the authorized `workspace_id`
outside the model-visible schema before invoking the existing application
service.

Require exactly one tool call for this narrow endpoint, disable parallel tool
calls, validate arguments again with Pydantic, reject unknown tools, and force
the final model turn to make no further tool calls. Return the executed tool
name with the answer so the UI makes the execution trace visible.

## Consequences

- A model cannot select or forge a workspace identifier.
- The initial execution budget is one read-only call with no agent loop.
- Tool output is treated as untrusted data and is separated from instructions.
- Provider failures, invalid calls, and invalid user input have stable HTTP
  error contracts.
- The endpoint always reads live KnowledgeBase metadata and does not use
  document chunks or vector retrieval.
- Additional tools require an explicit schema, authorization policy, execution
  budget, error contract, and tests before registration.
