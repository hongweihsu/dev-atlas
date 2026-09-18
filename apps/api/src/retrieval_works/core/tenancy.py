from uuid import UUID

# Stable compatibility target for data created before workspaces existed and for
# the explicitly enabled local development session. Normal runtime queries receive
# their workspace from authenticated membership resolution.
LEGACY_WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000002")
