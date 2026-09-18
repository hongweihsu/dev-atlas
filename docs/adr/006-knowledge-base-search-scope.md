# ADR-006: Use KnowledgeBase as an authorized search scope

- **Status:** Accepted; implemented
- **Date:** 2026-09-13

## Context

A workspace is Retrieval Works's tenant and permission boundary, but users also need a
smaller way to organize and search related documents. Passing arbitrary document
IDs from the browser would create unstable saved searches, large requests, and
an easy authorization surface to implement inconsistently.

Existing documents belong directly to workspaces and must remain available
during the transition.

## Decision

Introduce `KnowledgeBase` as a named retrieval scope owned by exactly one
workspace. In the first Phase 8 slice, each document belongs to exactly one
knowledge base. Search and answers may select one or more authorized knowledge
bases, but workspace membership remains the outer authorization boundary.

Keep `documents.workspace_id` alongside `documents.knowledge_base_id`. The
former makes tenant filters explicit and efficient; the latter selects retrieval
scope. A composite foreign key from `(workspace_id, knowledge_base_id)` to the
knowledge base guarantees both values describe the same tenant.

Each workspace may have at most one default knowledge base. The migration
creates `General` for every existing workspace, assigns every existing document
to its workspace's default, then makes `knowledge_base_id` non-null. New
documents use that default until the API exposes explicit selection.

## Alternatives considered

- Accept document-ID arrays as search scope: flexible but unstable, verbose,
  and easy to authorize inconsistently.
- Remove `documents.workspace_id` and derive tenancy through KnowledgeBase:
  normalized, but every security-sensitive document query would require a join
  and an omitted join could broaden scope.
- Allow documents in multiple knowledge bases: useful for tagging, but requires
  a join table and more complex lifecycle semantics before a real need exists.

## Consequences

The schema stores workspace ownership twice, so the composite foreign key is
mandatory. The default knowledge base preserves backward-compatible upload
behavior. The API validates the complete requested set before retrieval, then
globally ranks the combined candidate pool rather than assigning fixed per-base
quotas. React exposes creation, upload targeting, document filtering, and
multi-base question scope.
