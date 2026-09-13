# ADR-007: Use PostgreSQL-backed job state with ARQ dispatch

- **Status:** Accepted; implemented
- **Date:** 2026-09-13

## Context

Embedding a document can take longer than an interactive HTTP request and can
fail transiently. The synchronous upload route makes the browser wait and gives
the user no durable identifier with which to inspect progress or retry safely.

## Decision

Use PostgreSQL as the source of truth for ingestion requests, payloads, status,
attempts, errors, and results. Use Redis and ARQ to dispatch work to a separate
worker. `POST /ingestion-jobs` accepts an `Idempotency-Key` scoped to the active
workspace, validates the bounded text upload and KnowledgeBase authorization,
persists a queued job, and returns `202 Accepted`. The browser polls
`GET /ingestion-jobs/{id}` until `succeeded` or `failed`.

The worker transitions jobs through `queued -> processing -> succeeded|failed`.
It retries transient embedding-provider failures at most three times with
exponential delay. Each job UUID is also the intended new document UUID, so a
retry after the document transaction committed can recognize that same write
and converge rather than create a second document. Terminal jobs discard their
raw payload while retaining its SHA-256 checksum for safe idempotency checks.

## Alternatives considered

- FastAPI `BackgroundTasks`: simple, but work is tied to the API process and is
  not a durable queue or multi-process retry mechanism.
- Store all state only in Redis: fewer database writes, but user-visible history
  and result linkage would depend on an ephemeral infrastructure service.
- Build a queue from database polling: possible, but duplicates mature queue
  scheduling and retry behavior without a current product-specific need.

## Consequences

The API, worker, Redis, and PostgreSQL are separate operational components.
Redis is a wake-up mechanism; PostgreSQL remains authoritative. If PostgreSQL
commits a queued job but Redis dispatch fails, the API returns `503` and an
identical client retry with the same key safely re-dispatches it. Automatic
outbox recovery and object storage for large or long-lived payloads remain
future production-hardening work. Existing version replacement remains on the
synchronous route in this phase.
