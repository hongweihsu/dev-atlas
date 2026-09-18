from dataclasses import dataclass
from uuid import UUID

from retrieval_works.application.ports.agentic_research import (
    InvalidResearchQuestionError,
    ResearchAgent,
    ResearchResult,
)

MAX_RESEARCH_QUESTION_CHARACTERS = 2_000


@dataclass(frozen=True, slots=True)
class RunAgenticResearchCommand:
    question: str
    workspace_id: UUID


class RunAgenticResearch:
    def __init__(self, agent: ResearchAgent) -> None:
        self._agent = agent

    async def execute(self, command: RunAgenticResearchCommand) -> ResearchResult:
        question = command.question.strip()
        if not question:
            raise InvalidResearchQuestionError("question must not be empty")
        if len(question) > MAX_RESEARCH_QUESTION_CHARACTERS:
            raise InvalidResearchQuestionError(
                "question must not exceed "
                f"{MAX_RESEARCH_QUESTION_CHARACTERS} characters"
            )
        return await self._agent.research(question, workspace_id=command.workspace_id)
