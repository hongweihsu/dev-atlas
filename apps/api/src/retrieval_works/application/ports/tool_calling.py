from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class InvalidWorkspaceQuestionError(ValueError):
    """Raised when a workspace question violates the public contract."""


class InvalidToolCallError(ValueError):
    """Raised when the model returns a tool call outside the allowed contract."""


class WorkspaceToolProviderUnavailableError(RuntimeError):
    """Raised when the model provider cannot complete a tool-assisted answer."""


@dataclass(frozen=True, slots=True)
class ExecutedTool:
    name: str


@dataclass(frozen=True, slots=True)
class WorkspaceQuestionAnswer:
    text: str
    tools: tuple[ExecutedTool, ...]


class WorkspaceQuestionAnswerer(Protocol):
    async def answer(
        self, question: str, *, workspace_id: UUID
    ) -> WorkspaceQuestionAnswer: ...
