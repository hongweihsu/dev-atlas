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
- Phase 7 workspace ownership foundation with issuer/subject user identity,
  owner/editor/viewer memberships, non-null document tenancy, and a lossless
  migration path for existing single-user content
- PyJWT-backed bearer verification with pinned HS256, issuer, audience, expiry,
  and subject validation plus membership-resolved `GET /session` workspace context
- Server-enforced workspace isolation across ingestion, lists, lifecycle,
  versions, retrieval, and answers; Viewer is read-only while Editor and Owner
  may mutate documents
- Phase 8 KnowledgeBase persistence gives every document a workspace-consistent
  retrieval scope, with existing data migrated into a default `General` base
- Authorized KnowledgeBase management and selection across uploads, document
  lists, hybrid search, and grounded answers; one query can globally rank chunks
  from multiple selected bases while rejecting any cross-workspace scope ID
- An explicitly development-only session endpoint lets the local React app use
  the same authenticated API boundary without pretending to be production OIDC
- A provider-neutral RS256/JWKS verifier can validate externally issued access
  tokens with pinned issuer, audience, algorithm, expiry, and subject checks
- The React header displays the workspace name and role resolved by the server,
  making the active authorization context visible to the user
- Viewer sessions enter an explained read-only UI while the API independently
  enforces the same mutation boundary
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
  filename, and chunk count; the React workspace can sort by recent update or
  display name and select any listed document for a version update after reload
- Reversible `DELETE /documents/{document_id}` archival plus
  `POST /documents/{document_id}/restore`; archived documents are excluded from
  default lists and retrieval without deleting version or citation history
- React archive controls explain the reversible behavior, remove successful
  archives from the active list immediately, provide inline Undo, and include a
  persistent Archived view for later restoration
- Immutable version-history APIs and UI expose every retained source snapshot;
  users can atomically make an older version current without re-embedding or
  overwriting its chunks, while archived documents must be restored first
- Optional document display titles that default to the uploaded filename stem
- Workspace-scoped normalized-content duplicate protection for new writes,
  including concurrent requests, while preserving pre-existing historical rows
- OpenAI `text-embedding-3-small` adapter and FastAPI lifespan wiring, enabled
  only when `OPENAI_API_KEY` is configured
- Controlled live upload verified document, active-version, chunk, model, and
  1,536-dimensional vector persistence in PostgreSQL
- Hybrid chunk retrieval using pgvector cosine candidates, package-backed BM25
  candidates, and deterministic reciprocal-rank fusion
- Typed `POST /search` endpoint with bounded input, stable provider errors, and
  source/version/chunk provenance; verified through one controlled live query
- Bounded grounded-answer generation through `POST /answers`, with citations
  mapped back to document versions, chunks, source text, and character offsets
- React document workspace for text upload, persistent document selection,
  drag-and-drop input, tabbed create/version forms, consecutive version
  replacement, questions, answer sufficiency, and expandable citation provenance
- Docker Compose workflow for web, API, and database services
- Lightweight linting, formatting, type checking, and tests
- Retrieval-evaluation scaffold with a controlled five-document corpus,
  sixteen document-and-passage judgments, runtime UUID manifest, package-backed
  document metrics, and deterministic evidence-hit metrics
- Measured five-document ablation: vector, BM25, and hybrid Recall@1 were 0.875,
  1.000, and 0.938 respectively; the lexical-heavy corpus limitation is explicit
- Reproducible BM25S lifecycle benchmark with an explicit cache-review gate at
  1,000 active chunks or 25 ms measured rebuild p95

### Planned

- Persistent or cached lexical indexing when its measured review gate is reached
- External OIDC login UX
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
Docker Compose enables a local development-session issuer by default. That
issuer uses an in-memory browser token and a development signing secret; disable
`AUTH_DEVELOPMENT_MODE` and configure a production identity adapter before any
deployment. For an external provider, configure its HTTPS `AUTH_JWKS_URL`, exact
`AUTH_JWT_ISSUER`, and API `AUTH_JWT_AUDIENCE`, leaving the local signing secret
unset.

## Future direction

The current milestone is completed Phase 8 authorized search scope. Phase 9
adds asynchronous ingestion; production identity-provider UX and cloud
deployment follow in later milestones.

## Limitations

- Local token issuance is development-only; external login UX, membership
  administration, and background ingestion do not exist yet. The
  hybrid comparison covers only five controlled documents and must not be
  interpreted as general, large-scale, or multilingual search accuracy.
- Ingestion and grounded answers require an API key and incur provider usage.
- Re-ingestion currently embeds content before transactional duplicate
  detection, so a rejected duplicate may still incur embedding usage.
- The health endpoint currently reports API liveness, not database readiness.
- BM25 currently rebuilds an in-memory active-chunk index per search; its
  performance has not yet been benchmarked at representative corpus sizes.
