# ADR-016: Transactional ingestion outbox

## Status

Accepted — 2026-09-18

## Context

Writing a durable ingestion job to PostgreSQL and then publishing its ID to
Redis are two separate commits. If Redis fails between them, the job can remain
queued without ever reaching a worker.

## Decision

Insert one unique `ingestion_outbox_events` row in the same transaction as every
new ingestion job. An ARQ cron task scans at most 50 unpublished rows every ten
seconds with `FOR UPDATE SKIP LOCKED`, publishes the job UUID as ARQ's unique job
ID, and records `published_at` only after Redis accepts the enqueue operation.
Failures retain attempt count and a bounded error string for another sweep.

## Consequences

- Database commit becomes the API acceptance boundary during a Redis outage.
- Dispatch is at-least-once; the stable job ID and idempotent worker make
  duplicate publication safe.
- Enqueue latency can be up to roughly ten seconds.
- Outbox rows follow job retention through `ON DELETE CASCADE`.
