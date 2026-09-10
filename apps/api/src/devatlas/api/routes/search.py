from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from devatlas.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProviderUnavailableError,
)
from devatlas.application.search_documents import (
    InvalidSearchQueryError,
    SearchDocuments,
    SearchDocumentsCommand,
)


class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    strategy: Literal["vector", "lexical", "hybrid"] = "hybrid"


class SearchChunkResponse(BaseModel):
    document_id: str
    document_title: str
    version_id: str
    version_number: int
    chunk_id: str
    ordinal: int
    text: str
    start_offset: int
    end_offset: int
    similarity: float


class SearchResponse(BaseModel):
    results: list[SearchChunkResponse]


router = APIRouter(prefix="/search", tags=["search"])


def get_search_documents(request: Request) -> SearchDocuments:
    service = getattr(request.app.state, "search_documents", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "search_unavailable",
                "message": "document search is not configured",
            },
        )
    return cast(SearchDocuments, service)


SearchService = Annotated[SearchDocuments, Depends(get_search_documents)]


@router.post("", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    service: SearchService,
) -> SearchResponse:
    try:
        results = await service.execute(
            SearchDocumentsCommand(
                query=request.query,
                limit=request.limit,
                strategy=request.strategy,
            )
        )
    except InvalidSearchQueryError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_search", "message": str(error)},
        ) from error
    except EmbeddingBatchError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_embedding_response", "message": str(error)},
        ) from error
    except EmbeddingProviderUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "embedding_unavailable", "message": str(error)},
        ) from error

    return SearchResponse(
        results=[
            SearchChunkResponse(
                document_id=str(result.document_id),
                document_title=result.document_title,
                version_id=str(result.version_id),
                version_number=result.version_number,
                chunk_id=str(result.chunk_id),
                ordinal=result.ordinal,
                text=result.text,
                start_offset=result.start_offset,
                end_offset=result.end_offset,
                similarity=result.similarity,
            )
            for result in results
        ]
    )
