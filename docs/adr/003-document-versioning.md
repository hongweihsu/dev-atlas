# ADR-003: Version documents explicitly

- **Status:** Accepted; persistence structure implemented in Phase 1
- **Date:** 2026-08-19

## Context

Technical sources change. Overwriting chunks loses provenance, makes citations
ambiguous, and prevents auditing or rollback.

## Decision

Separate a logical Document from immutable DocumentVersion records. Chunks will
belong to a version. A SHA-256 content checksum will detect unchanged content.
When content changes, the initial implementation will re-parse, re-chunk, and
re-embed the entire document, activate the new version, and archive the previous
one.

## Alternatives considered

- Mutable documents/chunks: simpler but destroys history and citation clarity.
- Incremental chunk-level diffing: may reduce processing but introduces matching,
  ordering, and consistency complexity before workloads justify it.

## Trade-offs

Full reprocessing uses more compute and storage but is easier to reason about and
verify. Explicit versions add schema and lifecycle complexity.

## Consequences

Default retrieval will target active versions. Historical versions remain for
audit, rollback, provenance, and future comparison. Incremental ingestion remains
an explicitly deferred optimization.

The Phase 1 schema enforces unique version numbers and content checksums within
each document and permits at most one active version through a partial unique
index. `POST /documents/{document_id}/versions` locks the parent document so
concurrent updates serialize, rejects duplicate normalized content, calculates
the next consecutive number, and performs the active-version transition in one
transaction.
