# ADR-015: Self-service personal workspace onboarding

## Status

Accepted — 2026-09-17

## Context

The first deployed demo allowed only administrator-created Cognito users and
required a second operator command to create the corresponding Retrieval Works user and
membership. This made ordinary product signup depend on an administrator.

## Decision

Enable Cognito self-registration with email verification. After the first
successful OAuth login, the SPA calls authenticated `POST /session/bootstrap`
without a workspace header. The API trusts only the verified access token's
issuer and subject, then idempotently creates one local user, a Personal
Workspace when the user has no membership, an owner membership, and a default
General knowledge base.

The database locks the local user while checking membership so concurrent or
retried bootstrap requests converge on the same workspace. Existing provisioned
users keep their earliest membership. The response supplies the workspace ID;
all subsequent APIs continue to require `X-Workspace-ID` and database membership.

## Consequences

- A verified user can register, sign in, and begin using Retrieval Works without an
  operator editing the database.
- A valid Cognito token does not grant access to another user's workspace.
- The former fixed production `VITE_WORKSPACE_ID` is removed.
- Invitations, accepting another workspace, workspace selection, and
  editor/viewer administration were implemented as the collaboration follow-up.
- Public signup increases abuse and provider-cost exposure. Budget alarms remain
  required. Shared Redis fixed-window limits now protect workspace creation,
  invitations, and ingestion; broader distributed abuse controls remain beyond
  the low-traffic demo scope.
