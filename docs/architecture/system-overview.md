# System Overview

## Status

Phase 1 persistence foundation. This document distinguishes implemented
components from planned architecture.

## Implemented runtime

```text
Browser
  |
  | GET /api/health (development proxy)
  v
React + Vite
  |
  | GET /health (JSON)
  v
FastAPI
  |
  | async PostgreSQL connection
  v
PostgreSQL + pgvector
  |
  +-- Document -> DocumentVersion -> Chunk schema
```

Docker Compose runs one service for each boundary and gives them a private
network. A named volume preserves PostgreSQL data between normal restarts.

## Responsibilities

- **Web:** presentation, browser interaction, and API status display.
- **API:** HTTP contracts and the future application/domain boundary.
- **Database:** durable document/version/chunk metadata and vector storage. No
  upload or retrieval use case is connected yet.
- **Alembic:** explicit, reviewable database schema evolution.
- **Domain text processing:** deterministic line-ending normalization,
  normalized-content fingerprinting, traceable character-based chunks, and
  bounded UTF-8 plain-text preparation with stable validation codes.
- **Application ports:** provider-independent embedding contract with strict
  batch count, dimension, and finite-value validation. Routine tests use an
  offline deterministic fake.
- **Embedding adapter:** uses the async OpenAI client with
  `text-embedding-3-small`, explicit 1,536-dimensional float output, ordered
  result-index validation, and safe translation of SDK failures.
- **Ingestion application:** prepares a new document, creates traceable chunks,
  validates ordered embeddings, and stages the complete Version 1 aggregate
  behind a Unit of Work so persistence can commit or roll back atomically.
- **Persistence adapter:** maps the application ingestion record to a complete
  SQLAlchemy `Document -> DocumentVersion -> Chunk` aggregate. An async Unit of
  Work owns one session, commits once, and rolls back exceptions or uncommitted
  exits. A PostgreSQL integration test exercises this path against a migrated,
  disposable test database.
- **Upload API:** `POST /documents` accepts multipart title and file fields,
  reads at most one byte beyond the 1 MiB domain limit, and maps safe validation
  failures to stable `413`, `415`, and `422` responses. Tests inject offline
  embedding and persistence adapters. FastAPI lifespan wires the OpenAI and
  SQLAlchemy adapters when `OPENAI_API_KEY` is present; otherwise the endpoint
  intentionally returns `503 ingestion_unavailable`. Provider outages map to a
  safe `503`, while structurally incompatible provider output maps to `502`.
- **Retrieval application:** validates bounded queries, embeds each query once,
  and delegates ranking through a provider-independent search port.
- **Retrieval adapter:** computes pgvector cosine distance only across active
  versions with matching embedding model and dimension, orders the closest
  chunks first with a stable UUID tie-break, and returns document, version,
  chunk, text-offset, and similarity provenance. The HTTP search route is not
  connected yet.

The health endpoint is a liveness signal. It intentionally has no database query,
so a database incident does not make the API process itself appear dead. A
separate readiness check can be added when deployment requirements justify it.

## Failure cases

- If the API is unavailable, the web app displays an unavailable status.
- If PostgreSQL is unavailable, Compose does not start the dependent API until
  the database health check passes.
- If a future migration fails, startup should stop rather than silently creating
  or partially modifying application tables.

## Security boundary

There is no user authentication in Phase 0. Development CORS is limited to local
web origins. Future authorization must be enforced before or during retrieval;
unauthorized content must never enter model context.

## Planned evolution

The planned system adds document ingestion, retrieval, evaluation, workspace
authorization, asynchronous workers, and cloud infrastructure in later phases.
Those components are not part of the current runtime.
