from dataclasses import dataclass
from uuid import UUID

from devatlas.application.ports.embedding import (
    EmbeddingProvider,
    validate_embedding_batch,
)
from devatlas.application.ports.retrieval import (
    ChunkSearchRepository,
    RetrievalStrategy,
    RetrievedChunk,
)

MAX_QUERY_CHARACTERS = 2000
MAX_SEARCH_LIMIT = 20


class InvalidSearchQueryError(ValueError):
    """Raised when a search request violates the bounded query contract."""


@dataclass(frozen=True, slots=True)
class SearchDocumentsCommand:
    query: str
    workspace_id: UUID
    limit: int = 5
    strategy: RetrievalStrategy = "hybrid"


class SearchDocuments:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        repository: ChunkSearchRepository,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._repository = repository

    async def execute(self, command: SearchDocumentsCommand) -> list[RetrievedChunk]:
        query = command.query.strip()
        if not query:
            raise InvalidSearchQueryError("query must not be empty")
        if len(query) > MAX_QUERY_CHARACTERS:
            raise InvalidSearchQueryError(
                f"query must not exceed {MAX_QUERY_CHARACTERS} characters"
            )
        if not 1 <= command.limit <= MAX_SEARCH_LIMIT:
            raise InvalidSearchQueryError(
                f"limit must be between 1 and {MAX_SEARCH_LIMIT}"
            )

        embedding = None
        if command.strategy != "lexical":
            embeddings = await self._embedding_provider.embed([query])
            validate_embedding_batch(
                embeddings,
                expected_count=1,
                expected_dimension=self._embedding_provider.dimension,
            )
            embedding = embeddings[0]
        return await self._repository.search(
            query,
            embedding,
            workspace_id=command.workspace_id,
            model=self._embedding_provider.model,
            limit=command.limit,
            strategy=command.strategy,
        )
