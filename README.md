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
- Docker Compose workflow for web, API, and database services
- Lightweight linting, formatting, type checking, and tests

### Planned

- Document ingestion and source provenance
- Vector and lexical retrieval with measured evaluation
- Workspace-scoped authorization and explicit search scope
- Document versioning, asynchronous ingestion, and AWS deployment
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
[domain model](docs/architecture/domain-model.md).

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
the example values are development-only.

## Future direction

The next milestone will build a deliberately small document ingestion and
vector-RAG pipeline. Retrieval sophistication, multi-user authorization,
asynchronous processing, and cloud deployment come later and will be introduced
only with tests, documented trade-offs, and measurements where applicable.

## Limitations

- No RAG, LLM, ingestion, authentication, or workspace features exist yet.
- Document persistence and text preparation exist, but no upload endpoint,
  production embedding/persistence adapters, or retrieval API uses them yet.
- The health endpoint currently reports API liveness, not database readiness.
- No performance or quality benchmark claims have been made.
