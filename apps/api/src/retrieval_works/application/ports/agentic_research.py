from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from retrieval_works.application.ports.generation import EvidenceSource

type ResearchStopReason = Literal["completed", "tool_budget_reached"]


class InvalidResearchQuestionError(ValueError):
    """Raised when a research question violates the public contract."""


class InvalidResearchResponseError(ValueError):
    """Raised when a model response violates the bounded research contract."""


class ResearchProviderUnavailableError(RuntimeError):
    """Raised when the research model provider is unavailable."""


@dataclass(frozen=True, slots=True)
class ResearchStep:
    ordinal: int
    tool_name: str
    summary: str


@dataclass(frozen=True, slots=True)
class ResearchResult:
    answer: str
    has_sufficient_evidence: bool
    steps: tuple[ResearchStep, ...]
    citations: tuple[EvidenceSource, ...]
    stop_reason: ResearchStopReason


class ResearchAgent(Protocol):
    async def research(
        self, question: str, *, workspace_id: UUID
    ) -> ResearchResult: ...
