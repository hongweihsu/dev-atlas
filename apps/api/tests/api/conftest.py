from collections.abc import Iterator
from uuid import UUID

import pytest

from retrieval_works.api.dependencies.authentication import get_authorized_workspace
from retrieval_works.application.ports.workspace_access import AuthorizedWorkspace
from retrieval_works.main import app

TEST_WORKSPACE_ID = UUID(int=999)


@pytest.fixture(autouse=True)
def authorized_workspace() -> Iterator[None]:
    app.dependency_overrides[get_authorized_workspace] = lambda: AuthorizedWorkspace(
        user_id=UUID(int=998),
        workspace_id=TEST_WORKSPACE_ID,
        workspace_name="Test workspace",
        role="owner",
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_authorized_workspace, None)
