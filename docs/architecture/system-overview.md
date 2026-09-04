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
  offline deterministic fake; no production provider adapter is connected yet.

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
