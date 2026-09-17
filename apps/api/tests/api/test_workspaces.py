from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from devatlas.api.dependencies.authentication import (
    get_authenticated_principal,
    get_authorized_workspace,
)
from devatlas.api.routes.workspaces import router
from devatlas.application.ports.authentication import AuthenticatedPrincipal
from devatlas.application.ports.workspace_access import (
    AuthorizedWorkspace,
    WorkspaceInvitationResult,
    WorkspaceInvitationSummary,
    WorkspaceMember,
)


@pytest.fixture
def workspace_api() -> Iterator[tuple[TestClient, AsyncMock, AuthorizedWorkspace]]:
    application = FastAPI()
    application.include_router(router)
    principal = AuthenticatedPrincipal("https://identity.example", "user-subject")
    workspace = AuthorizedWorkspace(uuid4(), uuid4(), "Engineering", "owner")
    repository = AsyncMock()
    application.state.workspace_access_repository = repository
    application.dependency_overrides[get_authenticated_principal] = lambda: principal
    application.dependency_overrides[get_authorized_workspace] = lambda: workspace
    with TestClient(application) as client:
        yield client, repository, workspace


def test_user_can_list_and_create_workspaces(
    workspace_api: tuple[TestClient, AsyncMock, AuthorizedWorkspace],
) -> None:
    client, repository, existing = workspace_api
    created = AuthorizedWorkspace(existing.user_id, uuid4(), "Research", "owner")
    repository.list_for_principal.return_value = (existing, created)
    repository.create_workspace.return_value = created

    listed = client.get("/workspaces")
    response = client.post("/workspaces", json={"name": "  Research  "})

    assert listed.status_code == 200
    assert [item["workspace_name"] for item in listed.json()] == [
        "Engineering",
        "Research",
    ]
    assert response.status_code == 201
    assert response.json()["workspace_id"] == str(created.workspace_id)
    repository.create_workspace.assert_awaited_once_with(
        AuthenticatedPrincipal("https://identity.example", "user-subject"),
        "Research",
    )


def test_owner_can_create_email_bound_invitation(
    workspace_api: tuple[TestClient, AsyncMock, AuthorizedWorkspace],
) -> None:
    client, repository, workspace = workspace_api
    invitation_id = uuid4()
    repository.create_invitation.return_value = WorkspaceInvitationResult(
        invitation_id,
        "one-time-token",
        workspace.workspace_name,
        "reader@example.com",
        "viewer",
    )

    response = client.post(
        f"/workspaces/{workspace.workspace_id}/invitations",
        headers={"X-Workspace-ID": str(workspace.workspace_id)},
        json={"email": " Reader@Example.COM ", "role": "viewer"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "invitation_id": str(invitation_id),
        "token": "one-time-token",
        "workspace_name": "Engineering",
        "email": "reader@example.com",
        "role": "viewer",
    }
    repository.create_invitation.assert_awaited_once_with(
        workspace, "reader@example.com", "viewer"
    )


def test_invitation_rejects_a_different_verified_email(
    workspace_api: tuple[TestClient, AsyncMock, AuthorizedWorkspace],
) -> None:
    client, repository, _ = workspace_api
    repository.accept_invitation.side_effect = PermissionError(
        "invitation belongs to another email"
    )

    response = client.post(
        "/workspaces/invitations/accept",
        json={"token": "a-token-that-is-long-enough"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "invitation_email_mismatch"


def test_owner_lists_members_and_invitation_status(
    workspace_api: tuple[TestClient, AsyncMock, AuthorizedWorkspace],
) -> None:
    client, repository, workspace = workspace_api
    now = datetime.now(UTC)
    repository.list_members.return_value = (
        WorkspaceMember(
            workspace.user_id,
            "owner@example.com",
            "Owner",
            "owner",
            now,
        ),
    )
    repository.list_invitations.return_value = (
        WorkspaceInvitationSummary(
            uuid4(),
            "reader@example.com",
            "viewer",
            now + timedelta(days=1),
            None,
            now,
        ),
    )

    members = client.get(f"/workspaces/{workspace.workspace_id}/members")
    invitations = client.get(f"/workspaces/{workspace.workspace_id}/invitations")

    assert members.status_code == 200
    assert members.json()[0]["email"] == "owner@example.com"
    assert members.json()[0]["role"] == "owner"
    assert invitations.status_code == 200
    assert invitations.json()[0]["status"] == "pending"
    assert "token" not in invitations.json()[0]


def test_owner_membership_cannot_be_changed_or_removed(
    workspace_api: tuple[TestClient, AsyncMock, AuthorizedWorkspace],
) -> None:
    client, repository, workspace = workspace_api
    repository.update_member_role.side_effect = ValueError(
        "owner membership cannot be changed"
    )
    repository.remove_member.side_effect = ValueError(
        "owner membership cannot be removed"
    )

    changed = client.patch(
        f"/workspaces/{workspace.workspace_id}/members/{workspace.user_id}",
        json={"role": "viewer"},
    )
    removed = client.delete(
        f"/workspaces/{workspace.workspace_id}/members/{workspace.user_id}"
    )

    assert changed.status_code == 409
    assert changed.json()["detail"]["code"] == "protected_membership"
    assert removed.status_code == 409
    assert removed.json()["detail"]["code"] == "protected_membership"
