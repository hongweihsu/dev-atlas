from typing import Annotated, Literal, cast

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
    status: Literal["ready"]


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


def _validation_status(code: DocumentValidationCode) -> int:
    if code is DocumentValidationCode.UNSUPPORTED_TYPE:
        return status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    if code is DocumentValidationCode.FILE_TOO_LARGE:
        return status.HTTP_413_CONTENT_TOO_LARGE
    return status.HTTP_422_UNPROCESSABLE_CONTENT


@router.post(
    "", response_model=IngestDocumentResponse, status_code=status.HTTP_201_CREATED
)
async def ingest_document(
    file: Annotated[UploadFile, File()],
    service: IngestionService,
    title: Annotated[str, Form()] = "",
) -> IngestDocumentResponse:
    filename = file.filename or ""
    media_type = file.content_type or ""
    content = await file.read(DEFAULT_MAX_TEXT_BYTES + 1)

    try:
        result = await service.execute(
            IngestNewDocumentCommand(
                title=title,
                source_filename=filename,
                media_type=media_type,
                content=content,
            )
        )
    except DocumentValidationError as error:
        raise HTTPException(
            status_code=_validation_status(error.code),
            detail={"code": error.code, "message": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_title", "message": str(error)},
        ) from error

    return IngestDocumentResponse(
        document_id=str(result.document_id),
        version_id=str(result.version_id),
        filename=filename,
        checksum=result.checksum,
        chunk_count=result.chunk_count,
        status="ready",
    )
