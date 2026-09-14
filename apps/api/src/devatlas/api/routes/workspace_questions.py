from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from devatlas.api.dependencies.authentication import CurrentWorkspace
from devatlas.application.answer_workspace_question import (
    AnswerWorkspaceQuestion,
    AnswerWorkspaceQuestionCommand,
)
from devatlas.application.ports.tool_calling import (
    InvalidToolCallError,
    InvalidWorkspaceQuestionError,
    WorkspaceToolProviderUnavailableError,
)


class WorkspaceQuestionRequest(BaseModel):
    question: str


class ExecutedToolResponse(BaseModel):
    name: str


class WorkspaceQuestionResponse(BaseModel):
    answer: str
    tools: list[ExecutedToolResponse]


router = APIRouter(prefix="/workspace-questions", tags=["workspace-questions"])


def get_answer_workspace_question(request: Request) -> AnswerWorkspaceQuestion:
    service = getattr(request.app.state, "answer_workspace_question", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "workspace_questions_unavailable",
                "message": "workspace tool calling is not configured",
            },
        )
    return cast(AnswerWorkspaceQuestion, service)


WorkspaceQuestionService = Annotated[
    AnswerWorkspaceQuestion, Depends(get_answer_workspace_question)
]


@router.post("", response_model=WorkspaceQuestionResponse)
async def answer_workspace_question(
    payload: WorkspaceQuestionRequest,
    service: WorkspaceQuestionService,
    workspace: CurrentWorkspace,
) -> WorkspaceQuestionResponse:
    try:
        result = await service.execute(
            AnswerWorkspaceQuestionCommand(
                question=payload.question,
                workspace_id=workspace.workspace_id,
            )
        )
    except InvalidWorkspaceQuestionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_workspace_question", "message": str(error)},
        ) from error
    except InvalidToolCallError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_tool_call", "message": str(error)},
        ) from error
    except WorkspaceToolProviderUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "tool_provider_unavailable", "message": str(error)},
        ) from error

    return WorkspaceQuestionResponse(
        answer=result.text,
        tools=[ExecutedToolResponse(name=tool.name) for tool in result.tools],
    )
