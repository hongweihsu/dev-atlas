# Domain Model

## Status

The `Document`, `DocumentVersion`, and `Chunk` persistence slice is implemented
in Phase 1. User, workspace, membership, and knowledge-base entities remain
planned and are not enforced by the runtime.

DevAtlas will use the following conceptual ownership model unless a later ADR
changes it:

```text
User >--< WorkspaceMembership >-- Workspace
                                      |
                                      v
                                KnowledgeBase
                                      |
                                      v
                                  Document
                                      |
                                      v
                              DocumentVersion
                                      |
                                      v
                                    Chunk
```

Key invariants:

- A user may belong to multiple workspaces through memberships.
- A knowledge base belongs to exactly one workspace.
- V1 workspace members can access all knowledge bases in that workspace; there
  are no knowledge-base or document-level ACLs.
- Chunks belong to document versions, preserving provenance across updates.
- Retrieval must resolve identity, selected scope, and authorization before
  content can be selected for model context.

The implemented document tables enforce version-number and content-checksum
uniqueness per document, at most one active version per document, ordered chunk
identity per version, exact offset bounds, fixed 1,536-dimensional embeddings,
and cascading ownership. Re-ingestion locks the logical document, rejects an
existing normalized-content checksum, assigns the next version number, archives
the old active version, and creates the new active version in one transaction.
For new writes, the application additionally rejects a checksum found under any
logical document and returns that existing document's ID. This global policy is
transactionally serialized with a PostgreSQL advisory lock so historical
duplicates can remain without weakening concurrency protection for future
writes.

The remaining entities will receive concrete schemas, constraints, indexes, and
security tests only in the phases that implement them.

Phase 6 adds a reversible lifecycle boundary to the logical document.
`archived_at` is null while a document participates in default lists and
retrieval. Archiving sets the timestamp but preserves all versions, chunks,
embeddings, and citation provenance; restoring clears it. Permanent cascading
deletion is intentionally a separate, higher-risk operation.

An active document exposes all retained immutable versions through its history.
Activating a historical version changes only version-selection state: all
versions for the document become inactive and the chosen version becomes active
in one transaction. It does not copy content, re-chunk, re-embed, or change the
version number. The next uploaded revision still uses `max(version_number) + 1`.

For the current upload-only product, `Document.id` is the stable logical
identity and each version's filename, media type, checksum, and creation time
are sufficient snapshot provenance. Phase 6 deliberately does not add a
speculative reusable `Source` table: URL and connector sources do not exist yet,
and their stable external keys and synchronization lifecycle are still unknown.
The first additional source type will supply the evidence needed to design that
boundary without an expensive premature migration.
