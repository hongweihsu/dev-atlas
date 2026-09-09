# DevAtlas

**AI Technical Research & Knowledge Platform**

DevAtlas is a learning-first, production-oriented AI engineering project for
organizing and researching technical knowledge. It will grow deliberately from
a full-stack foundation into a measured, permission-aware retrieval system.

## Current status

### Implemented

- React, Vite, and TypeScript web application
- FastAPI service with a typed `GET /health` endpoint
- PostgreSQL development service with pgvector available
- Alembic migration infrastructure and an initial document/version/chunk schema
- Deterministic text normalization, SHA-256 fingerprinting, and traceable
  character-based chunking
- Framework-independent validation and preparation for bounded UTF-8 text files
- Provider-independent new-document ingestion orchestration with an atomic
  persistence boundary and deterministic test doubles
- Async SQLAlchemy repository and Unit of Work adapters, verified against a
  migrated disposable PostgreSQL database
- Typed `POST /documents` multipart boundary with bounded reads and stable
  validation errors, tested through dependency-injected offline adapters
- Atomic `POST /documents/{document_id}/versions` re-ingestion: changed content
  receives the next consecutive version, the previous version is archived, and
  duplicate normalized content returns a stable conflict
- Persistent `GET /documents` catalog with each document's active version,
  filename, and chunk count; the React workspace can select any listed document
  for a version update after a page reload
- Global normalized-content duplicate protection for new writes, including
  concurrent requests, while preserving pre-existing historical rows
- OpenAI `text-embedding-3-small` adapter and FastAPI lifespan wiring, enabled
  only when `OPENAI_API_KEY` is configured
- Controlled live upload verified document, active-version, chunk, model, and
  1,536-dimensional vector persistence in PostgreSQL
- Provider-independent search orchestration and pgvector cosine retrieval over
  compatible chunks from active document versions
- Typed `POST /search` endpoint with bounded input, stable provider errors, and
  source/version/chunk provenance; verified through one controlled live query
- Bounded grounded-answer generation through `POST /answers`, with citations
  mapped back to document versions, chunks, source text, and character offsets
- React document workspace for text upload, persistent document selection,
  consecutive version replacement, questions, answer sufficiency, and
  expandable citation provenance
- Docker Compose workflow for web, API, and database services
- Lightweight linting, formatting, type checking, and tests

### Planned

- Vector and lexical retrieval with measured evaluation
- Workspace-scoped authorization and explicit search scope
- Asynchronous ingestion and AWS deployment
- Multimodal document understanding and bounded research workflows

Planned capabilities are not implemented or benchmarked yet.

## Architecture

```text
Browser
  | HTTP / JSON
  v
React + Vite  --->  FastAPI  --->  PostgreSQL + pgvector
   web               api             database
```

The browser calls the API; the API owns access to persistent data. During local
development, Vite proxies `/api` requests to FastAPI. See the
[system overview](docs/architecture/system-overview.md) and
[domain model](docs/architecture/domain-model.md). Phase 1 verification is
recorded in the [acceptance record](docs/verification/phase-1-acceptance.md).

## Local setup

### Docker Compose (recommended)

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:5173>. The API health endpoint is available at
<http://localhost:8000/health>.

Stop the stack with:

```bash
docker compose down
```

Add `--volumes` only when you intentionally want to remove local database data.

### Run checks locally

Backend dependencies require Python 3.12 or 3.13:

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy
pytest
```

Frontend:

```bash
cd apps/web
pnpm install
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

## Configuration

Copy `.env.example` to `.env` for local defaults. `.env` is ignored by Git.
Production credentials must be supplied through an appropriate secrets system;
the example values are development-only. Set `OPENAI_API_KEY` to enable live
document ingestion; leave it empty to keep the endpoint safely unavailable.

## Future direction

The next milestone establishes a small reviewed retrieval baseline and makes
one package-adoption decision before adding hybrid search. Multi-user
authorization, asynchronous processing, and cloud deployment come later.

## Limitations

- No authentication, workspace isolation, background ingestion, hybrid search,
  or retrieval-quality benchmark exists yet.
- Ingestion and grounded answers require an API key and incur provider usage.
- Re-ingestion currently embeds content before transactional duplicate
  detection, so a rejected duplicate may still incur embedding usage.
- The health endpoint currently reports API liveness, not database readiness.
- No performance or quality benchmark claims have been made.
