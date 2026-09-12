# ADR-002: Use workspace-scoped authorization in V1

- **Status:** Accepted and implemented for document operations
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

Phase 7 begins with `User`, `Workspace`, and `WorkspaceMembership` tables and a
non-null `documents.workspace_id` ownership key. Until Phase 8 introduces
selectable knowledge bases, documents belong directly to a workspace; this
keeps the tenant boundary enforceable without inventing an unused scope layer.
External identity is keyed by issuer plus subject rather than email because
email is mutable and need not be unique across identity providers.

Existing single-user documents migrate into a deterministic personal workspace
owned by a legacy local identity. This is a compatibility bridge, not the final
request authentication mechanism. Every document read and mutation is now
scoped from an authenticated membership.

The first authentication adapter uses FastAPI's HTTP Bearer dependency and
PyJWT with a server-pinned HS256 algorithm, configured secret, issuer, audience,
required expiry, and required subject. Tokens establish identity only; the
database membership remains the authority for workspace access and role. The
local symmetric verifier is an adapter boundary that can later be replaced by
an external OIDC/JWKS verifier without changing workspace policy.

For local development only, an explicitly enabled endpoint issues an eight-hour
token for the migrated personal-workspace owner. The React client keeps this
token in memory and sends both the Bearer credential and selected workspace ID.
This preserves the real authorization path during development, but it is not a
production login mechanism and is disabled by default in application settings.

Document reads require membership. Document mutations additionally require the
Owner or Editor role; Viewer is read-only. Repository queries include the
authorized workspace ID, so guessing a document UUID from another workspace
produces the same not-found result as an unknown UUID.

## Alternatives considered

- `user.workspace_id`: cannot represent membership in multiple workspaces.
- Knowledge-base/document ACLs: more flexible but add policy complexity that V1
  does not require.
- Public workspaces: broaden discovery and moderation concerns too early.

## Trade-offs

Workspace-level policy is understandable and testable but cannot express private
knowledge bases within one shared workspace.

## Consequences

Future resource types must follow the same rule: validate selected scope against
membership before querying. Integration coverage proves cross-workspace list,
search, version, and lifecycle denial; API coverage proves Viewer write denial.
