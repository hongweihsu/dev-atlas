from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from devatlas.api.dependencies.authentication import (
    CurrentPrincipal,
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
