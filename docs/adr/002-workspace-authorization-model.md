# ADR-002: Use workspace-scoped authorization in V1

- **Status:** Proposed; implementation is planned for a later phase
- **Date:** 2026-08-19

## Context

DevAtlas needs collaboration boundaries without prematurely building enterprise
IAM or fine-grained ACLs. Users may participate in multiple groups with different
roles.

## Decision

Model users and workspaces as many-to-many through workspace memberships with
Owner, Editor, and Viewer roles. A knowledge base belongs to one workspace. In
V1, workspace membership grants access to every knowledge base in that workspace.
Personal workspaces are private, shared workspaces are invitation-only, and
system knowledge is read-only to normal users.

Authorization will be resolved before or during retrieval. The model prompt is
not an authorization boundary.

## Alternatives considered

- `user.workspace_id`: cannot represent membership in multiple workspaces.
- Knowledge-base/document ACLs: more flexible but add policy complexity that V1
  does not require.
- Public workspaces: broaden discovery and moderation concerns too early.

## Trade-offs

Workspace-level policy is understandable and testable but cannot express private
knowledge bases within one shared workspace.

## Consequences

Future retrieval queries must validate selected scope against memberships and
roles. Security tests must prove cross-workspace isolation and role enforcement.
