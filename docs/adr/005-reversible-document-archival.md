# ADR-005: Archive documents before permanent deletion

- **Status:** Accepted; backend lifecycle implemented in Phase 6
- **Date:** 2026-09-12

## Context

Deleting a logical document with database cascades would immediately remove all
versions, chunks, embeddings, and citation provenance. Users need to remove a
document from normal use without turning an accidental click into irreversible
data loss.

## Decision

Add nullable `documents.archived_at`. `DELETE /documents/{document_id}` archives
the logical document instead of physically deleting it, and
`POST /documents/{document_id}/restore` reverses that transition. Default
document lists, vector retrieval, and BM25 retrieval select only documents where
`archived_at IS NULL`.

Versions and chunks remain unchanged while archived. Both transitions lock and
update the document in one database transaction and are idempotent for an
existing document.

## Alternatives considered

- Hard delete immediately: simpler storage behavior but destroys audit history,
  embeddings, and citation provenance.
- Set every version inactive: overloads version state and loses the distinction
  between the current version and the logical document's lifecycle.
- Add a general status enum immediately: supports more future states but adds
  state transitions with no current user requirement.

## Consequences

Archival is safe and reversible, but storage is not reclaimed. The frontend
removes archived documents from the active list immediately and offers inline
Undo/restore. A future permanent-delete operation must be separately authorized
and should communicate that cascades remove versions and chunks. A persistent
archived-document browser remains future work; Undo currently lasts for the
page session.
