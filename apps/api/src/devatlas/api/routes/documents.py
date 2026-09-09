from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel

from devatlas.application.ingest_document import (
    IngestNewDocument,
    IngestNewDocumentCommand,
    InvalidDocumentTitleError,
)
from devatlas.application.list_documents import ListDocuments
from devatlas.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProviderUnavailableError,
)
from devatlas.application.ports.persistence import (
    DocumentNotFoundError,
    DuplicateDocumentContentError,
)
from devatlas.domain.document_ingestion import (
    DEFAULT_MAX_TEXT_BYTES,
    DocumentValidationCode,
    DocumentValidationError,
)


class IngestDocumentResponse(BaseModel):
    document_id: str
    version_id: str
    filename: str
    checksum: str
    chunk_count: int
    version_number: int
    status: Literal["ready"]


class DocumentSummaryResponse(BaseModel):
    document_id: str
    title: str
    active_version_id: str
    active_version_number: int
    source_filename: str
    chunk_count: int
    updated_at: datetime


router = APIRouter(prefix="/documents", tags=["documents"])


def get_ingest_new_document(request: Request) -> IngestNewDocument:
    """Resolve runtime wiring without constructing infrastructure in the route."""
    service = getattr(request.app.state, "ingest_new_document", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "ingestion_unavailable",
                "message": "document ingestion is not configured",
            },
        )
    return cast(IngestNewDocument, service)


IngestionService = Annotated[IngestNewDocument, Depends(get_ingest_new_document)]


def get_list_documents(request: Request) -> ListDocuments:
    service = getattr(request.app.state, "list_documents", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "document_catalog_unavailable",
                "message": "document catalog is not configured",
            },
        )
    return cast(ListDocuments, service)


DocumentListService = Annotated[ListDocuments, Depends(get_list_documents)]


def _validation_status(code: DocumentValidationCode) -> int:
    if code is DocumentValidationCode.UNSUPPORTED_TYPE:
        return status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    if code is DocumentValidationCode.FILE_TOO_LARGE:
        return status.HTTP_413_CONTENT_TOO_LARGE
    return status.HTTP_422_UNPROCESSABLE_CONTENT


@router.get("", response_model=list[DocumentSummaryResponse])
async def list_documents(service: DocumentListService) -> list[DocumentSummaryResponse]:
    documents = await service.execute()
    return [
        DocumentSummaryResponse(
            document_id=str(document.document_id),
            title=document.title,
            active_version_id=str(document.active_version_id),
            active_version_number=document.active_version_number,
            source_filename=document.source_filename,
            chunk_count=document.chunk_count,
            updated_at=document.updated_at,
        )
        for document in documents
    ]


@router.post(
    "", response_model=IngestDocumentResponse, status_code=status.HTTP_201_CREATED
)
async def ingest_document(
    file: Annotated[UploadFile, File()],
    service: IngestionService,
    title: Annotated[str, Form()] = "",
) -> IngestDocumentResponse:
    return await _ingest(file=file, title=title, service=service)


@router.post(
    "/{document_id}/versions",
    response_model=IngestDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_document_version(
    document_id: UUID,
    file: Annotated[UploadFile, File()],
    service: IngestionService,
) -> IngestDocumentResponse:
    return await _ingest(
        file=file,
        title="",
        service=service,
        document_id=document_id,
    )


async def _ingest(
    *,
    file: UploadFile,
    title: str,
    service: IngestNewDocument,
    document_id: UUID | None = None,
) -> IngestDocumentResponse:
    filename = file.filename or ""
    media_type = file.content_type or ""
    content = await file.read(DEFAULT_MAX_TEXT_BYTES + 1)
    resolved_title = title
    if document_id is None and not title.strip():
        filename_without_path = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        resolved_title = filename_without_path.rsplit(".", 1)[0] or "Untitled document"

    try:
        command = IngestNewDocumentCommand(
            title=resolved_title,
            source_filename=filename,
            media_type=media_type,
            content=content,
        )
        if document_id is None:
            result = await service.execute(command)
        else:
            result = await service.execute_version(document_id, command)
    except DocumentValidationError as error:
        raise HTTPException(
            status_code=_validation_status(error.code),
            detail={"code": error.code, "message": str(error)},
        ) from error
    except InvalidDocumentTitleError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_title", "message": str(error)},
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
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "document_not_found", "message": str(error)},
        ) from error
    except DuplicateDocumentContentError as error:
        detail: dict[str, str] = {
            "code": "duplicate_document_content",
            "message": str(error),
        }
        if error.document_id is not None:
            detail["document_id"] = str(error.document_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from error

    return IngestDocumentResponse(
        document_id=str(result.document_id),
        version_id=str(result.version_id),
        filename=filename,
        checksum=result.checksum,
        chunk_count=result.chunk_count,
        version_number=result.version_number,
        status="ready",
    )
