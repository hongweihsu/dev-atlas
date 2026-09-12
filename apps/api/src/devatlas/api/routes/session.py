from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from devatlas.api.dependencies.authentication import CurrentWorkspace


class SessionResponse(BaseModel):
    user_id: str
    workspace_id: str
    workspace_name: str
    role: Literal["owner", "editor", "viewer"]


router = APIRouter(prefix="/session", tags=["session"])


@router.get("", response_model=SessionResponse)
async def get_session(workspace: CurrentWorkspace) -> SessionResponse:
    return SessionResponse(
        user_id=str(workspace.user_id),
        workspace_id=str(workspace.workspace_id),
        workspace_name=workspace.workspace_name,
        role=workspace.role,
    )
