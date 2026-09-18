from typing import Protocol


class CorrectiveQueryProviderUnavailableError(RuntimeError):
    """Raised when the corrective-query provider cannot produce a rewrite."""


class CorrectiveQueryGenerator(Protocol):
    async def rewrite(self, question: str, failed_answer: str) -> str: ...
