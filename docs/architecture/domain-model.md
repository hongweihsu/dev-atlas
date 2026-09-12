# Domain Model

## Status

The document/version/chunk persistence slice and the Phase 7 user, workspace,
membership, authentication, and query-level document isolation are implemented.
Knowledge-base scope and production identity-provider integration remain
planned work.

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
logical document in the authorized workspace and returns that existing
document's ID. This workspace-scoped policy is transactionally serialized with
a PostgreSQL advisory lock so historical duplicates can remain without
weakening concurrency protection for future writes.

Every current document query receives the workspace resolved from a validated
credential and database membership. Reads allow all membership roles; writes
allow Owner and Editor. The browser-provided workspace ID selects a desired
scope but cannot grant access by itself.

Phase 7 stores external identity as `(identity_issuer, identity_subject)`, models
workspace membership with one of `owner`, `editor`, or `viewer`, and requires
every document to reference a workspace. The migration assigns all pre-workspace
documents to a deterministic legacy personal workspace so no existing content
becomes ownerless. Documents currently attach directly to workspaces; the
KnowledgeBase relationship in the conceptual model remains a Phase 8 search-
scope concern.

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
