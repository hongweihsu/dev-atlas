# System Overview

## Status

Phase 9 permission-aware retrieval and asynchronous ingestion. This document
distinguishes implemented components from planned architecture.

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
FastAPI ------------------> PostgreSQL + pgvector
  |                         job state + documents
  v
Redis / ARQ queue -------> ingestion worker
                            |
                            +----> OpenAI embeddings
                            +----> PostgreSQL transaction
```

Docker Compose runs one service for each boundary and gives them a private
network. A named volume preserves PostgreSQL data between normal restarts.

## Responsibilities

- **Web:** persistent document catalog and selection, document upload and
  replacement-version forms, questions, grounded answers, expandable citation
  provenance, and actionable API availability feedback.
- **API:** HTTP contracts and the application/domain boundary.
- **Database:** durable document/version/chunk metadata and vector storage.
- **Alembic:** explicit, reviewable database schema evolution.
- **Redis/ARQ:** lightweight dispatch and bounded retry scheduling; Redis does
  not replace durable PostgreSQL job state.
- **Ingestion worker:** claims queued jobs, invokes the existing ingestion use
  case outside the HTTP process, records attempts and terminal result/error
  provenance, and recognizes an already-committed deterministic document ID.
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
- **Version API:** `POST /documents/{document_id}/versions` accepts replacement
  content for a logical document. A row lock serializes concurrent updates;
  duplicate normalized content returns `409`, missing documents return `404`,
  and the old-active/new-active transition commits atomically.
- **Catalog API:** `GET /documents` returns each logical document with its active
  version ID and number, source filename, chunk count, and update time. It is
  available whenever the database is configured and does not require an OpenAI
  key.
- **Duplicate-write policy:** all new document/version writes reject normalized
  content already stored anywhere in the catalog. A checksum-derived PostgreSQL
  advisory transaction lock serializes concurrent candidates before an exact
  checksum lookup. Historical duplicate rows remain untouched.
- **Retrieval application:** validates bounded queries, embeds each query once,
  and delegates ranking through a provider-independent search port.
- **Retrieval adapters:** pgvector ranks compatible active-version chunks by
  cosine distance while BM25S ranks a snapshot of current active chunks by
  lexical relevance. Deterministic reciprocal-rank fusion combines candidate
  positions by stable chunk UUID instead of adding incomparable raw scores.
  Search responses expose a generic `score` plus `scoring_method`; an RRF value
  is never described as cosine similarity.
  The first bounded BM25 slice rebuilds its in-memory index per search; this is
  explicit technical debt rather than a production-scale latency claim.
- **Search API:** `POST /search` accepts a bounded JSON query and result limit,
  maps known embedding failures to stable `502`/`503` responses, and returns
  ranked chunk evidence with full provenance. A controlled live query retrieved
  the retained ingestion fixture; the observed score is not a quality claim.
- **Answer API:** `POST /answers` retrieves bounded evidence, asks the configured
  model for structured output, validates citation identifiers, and returns
  source text plus document/version/chunk/offset provenance. Empty retrieval
  returns a deterministic insufficient-evidence response without generation.

The health endpoint is a liveness signal. It intentionally has no database query,
so a database incident does not make the API process itself appear dead. A
separate readiness check can be added when deployment requirements justify it.

## Failure cases

- If the API is unavailable, the web app displays a retryable banner and
  disables upload and answer actions.
- If PostgreSQL is unavailable, Compose does not start the dependent API until
  the database health check passes.
- If a future migration fails, startup should stop rather than silently creating
  or partially modifying application tables.

## Security boundary

There is no user authentication in Phase 0. Development CORS is limited to local
web origins. Future authorization must be enforced before or during retrieval;
unauthorized content must never enter model context.

## Planned evolution

The planned system adds cloud infrastructure, additional content loaders,
bounded agent workflows, and production observability in later phases.
