from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from devatlas.api.dependencies.authentication import (
    CurrentPrincipal,
    WritableWorkspace,
    get_authorized_workspace,
)
from devatlas.api.routes.session import router
from devatlas.application.ports.authentication import AuthenticatedPrincipal
from devatlas.application.ports.workspace_access import AuthorizedWorkspace


def test_missing_bearer_token_is_rejected_with_challenge() -> None:
    application = FastAPI()

    @application.get("/protected")
    def protected(principal: CurrentPrincipal) -> dict[str, str]:
        return {"subject": principal.subject}

    application.state.token_verifier = Mock()

    response = TestClient(application).get("/protected")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"]["code"] == "invalid_credentials"


def test_session_returns_only_authorized_workspace_context() -> None:
    user_id = uuid4()
    workspace_id = uuid4()
    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_authorized_workspace] = lambda: (
        AuthorizedWorkspace(
            user_id=user_id,
            workspace_id=workspace_id,
            workspace_name="Engineering",
            role="editor",
        )
    )

    response = TestClient(application).get("/session")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(user_id),
        "workspace_id": str(workspace_id),
        "workspace_name": "Engineering",
        "role": "editor",
    }


def test_bootstrap_creates_or_returns_personal_workspace_without_header() -> None:
    user_id = uuid4()
    workspace_id = uuid4()
    application = FastAPI()
    application.include_router(router)
    verifier = Mock()
    principal = AuthenticatedPrincipal(
        issuer="https://identity.example", subject="new-user-subject"
    )
    verifier.verify.return_value = principal
    repository = AsyncMock()
    repository.bootstrap_personal_workspace.return_value = AuthorizedWorkspace(
        user_id=user_id,
        workspace_id=workspace_id,
        workspace_name="Personal Workspace",
        role="owner",
    )
    application.state.token_verifier = verifier
    application.state.workspace_access_repository = repository

    response = TestClient(application).post(
        "/session/bootstrap",
        headers={"Authorization": "Bearer signed-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(user_id),
        "workspace_id": str(workspace_id),
        "workspace_name": "Personal Workspace",
        "role": "owner",
    }
    repository.bootstrap_personal_workspace.assert_awaited_once_with(principal)


def test_cognito_bootstrap_uses_matching_verified_identity_claims() -> None:
    application = FastAPI()
    application.include_router(router)
    access_verifier = Mock()
    access_verifier.verify.return_value = AuthenticatedPrincipal(
        issuer="https://identity.example", subject="user-subject"
    )
    identity = AuthenticatedPrincipal(
        issuer="https://identity.example",
        subject="user-subject",
        email="reader@example.com",
    )
    identity_verifier = Mock()
    identity_verifier.verify.return_value = identity
    repository = AsyncMock()
    repository.bootstrap_personal_workspace.return_value = AuthorizedWorkspace(
        uuid4(), uuid4(), "Personal Workspace", "owner"
    )
    application.state.token_verifier = access_verifier
    application.state.identity_token_verifier = identity_verifier
    application.state.workspace_access_repository = repository

    response = TestClient(application).post(
        "/session/bootstrap",
        headers={
            "Authorization": "Bearer access-token",
            "X-Identity-Token": "identity-token",
        },
    )

    assert response.status_code == 200
    identity_verifier.verify.assert_called_once_with("identity-token")
    repository.bootstrap_personal_workspace.assert_awaited_once_with(identity)


def test_cognito_bootstrap_rejects_mismatched_token_subjects() -> None:
    application = FastAPI()
    application.include_router(router)
    access_verifier = Mock()
    access_verifier.verify.return_value = AuthenticatedPrincipal(
        issuer="https://identity.example", subject="access-subject"
    )
    identity_verifier = Mock()
    identity_verifier.verify.return_value = AuthenticatedPrincipal(
        issuer="https://identity.example",
        subject="different-subject",
        email="reader@example.com",
    )
    application.state.token_verifier = access_verifier
    application.state.identity_token_verifier = identity_verifier
    application.state.workspace_access_repository = AsyncMock()

    response = TestClient(application).post(
        "/session/bootstrap",
        headers={
            "Authorization": "Bearer access-token",
            "X-Identity-Token": "identity-token",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "identity_mismatch"


def test_workspace_membership_denial_does_not_return_session() -> None:
    application = FastAPI()
    application.include_router(router)
    verifier = Mock()
    verifier.verify.return_value = AuthenticatedPrincipal(
        issuer="devatlas-local", subject="personal-owner"
    )
    repository = AsyncMock()
    repository.resolve.return_value = None
    application.state.token_verifier = verifier
    application.state.workspace_access_repository = repository

    response = TestClient(application).get(
        "/session",
        headers={
            "Authorization": "Bearer signed-token",
            "X-Workspace-ID": str(uuid4()),
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "workspace_access_denied"


def test_viewer_cannot_use_a_workspace_write_dependency() -> None:
    application = FastAPI()

    @application.post("/write")
    def write(workspace: WritableWorkspace) -> dict[str, str]:
        return {"workspace_id": str(workspace.workspace_id)}

    application.dependency_overrides[get_authorized_workspace] = lambda: (
        AuthorizedWorkspace(
            user_id=uuid4(),
            workspace_id=uuid4(),
            workspace_name="Read only",
            role="viewer",
        )
    )

    response = TestClient(application).post("/write")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "workspace_write_denied"
