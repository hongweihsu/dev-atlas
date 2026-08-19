# ADR-001: Use PostgreSQL with pgvector

- **Status:** Accepted for the foundation; vector retrieval is not implemented
- **Date:** 2026-08-19

## Context

DevAtlas needs relational data for users, ownership, documents, conversations,
and evaluation. It will later need vector similarity search. Phase 0 needs a
local database without prematurely operating multiple data stores.

## Decision

Use PostgreSQL as the primary database and a PostgreSQL image that includes the
pgvector extension. Manage future schema changes with Alembic.

## Alternatives considered

- A separate managed vector database: potentially useful at larger scale but
  adds another operational and consistency boundary before there is evidence.
- OpenSearch/Elasticsearch: strong lexical and distributed search capabilities,
  but excessive for the foundation and early experiments.
- SQLite: simple locally, but does not represent the intended PostgreSQL/vector
  environment closely enough.

## Trade-offs

One database simplifies transactions, backups, metadata filtering, and local
operations. PostgreSQL vector search may eventually face scaling or search-feature
limits compared with specialized systems.

## Consequences

Early retrieval experiments can combine relational metadata and vectors in one
system. A later benchmark may justify adding or moving to specialized search
infrastructure; no such claim is made now.
