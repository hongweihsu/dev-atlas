from uuid import UUID

# Migration target for data created before workspaces existed. Runtime scoping will
# replace this compatibility default with the authenticated workspace in Phase 7.
LEGACY_WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000002")
