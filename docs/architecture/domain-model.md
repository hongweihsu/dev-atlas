# Domain Model

## Status

Planned and deliberately not implemented in Phase 0.

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

No domain tables are created yet. Their concrete schema, constraints, indexes,
and security tests will be designed in the phases that implement them.
