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
and cascading ownership. Cross-table provenance and lifecycle transitions still
require application and integration tests in the ingestion slice.

The remaining entities will receive concrete schemas, constraints, indexes, and
security tests only in the phases that implement them.
