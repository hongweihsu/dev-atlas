# ADR-003: Version documents explicitly

- **Status:** Proposed; implementation is planned for a later phase
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
