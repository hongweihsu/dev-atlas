from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel

from devatlas.api.dependencies.authentication import CurrentWorkspace, WritableWorkspace
from devatlas.api.routes.knowledge_bases import get_manage_knowledge_bases
from devatlas.application.manage_ingestion_jobs import (
    InvalidIdempotencyKeyError,
    ManageIngestionJobs,
)
from devatlas.application.ports.ingestion_jobs import (
    IdempotencyConflictError,
    IngestionJobNotFoundError,
    IngestionJobSnapshot,
    IngestionJobStatus,
    IngestionQueueUnavailableError,
)
from devatlas.application.ports.knowledge_bases import InvalidKnowledgeBaseScopeError
from devatlas.domain.document_ingestion import (
    DEFAULT_MAX_UPLOAD_BYTES,
    DocumentValidationCode,
    DocumentValidationError,
    validate_document_upload,
)


class IngestionJobResponse(BaseModel):
    id: UUID
    status: IngestionJobStatus
    attempt_count: int
    document_id: UUID | None
    version_id: UUID | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


router = APIRouter(prefix="/ingestion-jobs", tags=["ingestion-jobs"])


def get_manage_ingestion_jobs(request: Request) -> ManageIngestionJobs:
    service = getattr(request.app.state, "manage_ingestion_jobs", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "ingestion_queue_unavailable",
                "message": "asynchronous ingestion is not configured",
            },
        )
    return cast(ManageIngestionJobs, service)


JobService = Annotated[ManageIngestionJobs, Depends(get_manage_ingestion_jobs)]


def _response(snapshot: IngestionJobSnapshot) -> IngestionJobResponse:
    return IngestionJobResponse.model_validate(snapshot, from_attributes=True)


def _validation_status(code: DocumentValidationCode) -> int:
    if code is DocumentValidationCode.UNSUPPORTED_TYPE:
        return status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    if code is DocumentValidationCode.FILE_TOO_LARGE:
        return status.HTTP_413_CONTENT_TOO_LARGE
    return status.HTTP_422_UNPROCESSABLE_CONTENT


@router.post(
    "", response_model=IngestionJobResponse, status_code=status.HTTP_202_ACCEPTED
)
async def submit_ingestion_job(
    request: Request,
    file: Annotated[UploadFile, File()],
    service: JobService,
    workspace: WritableWorkspace,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    knowledge_base_id: Annotated[UUID, Form()],
    title: Annotated[str, Form()] = "",
) -> IngestionJobResponse:
    content = await file.read(DEFAULT_MAX_UPLOAD_BYTES + 1)
    filename = file.filename or ""
    media_type = file.content_type or ""
    resolved_title = title.strip() or filename.rsplit(".", 1)[0] or "Untitled document"
    if len(resolved_title) > 255:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "invalid_ingestion_job",
                "message": "title must not exceed 255 characters",
            },
        )
    try:
        validate_document_upload(
            content=content, source_filename=filename, media_type=media_type
        )
        scope = await get_manage_knowledge_bases(request).resolve_scope(
            workspace.workspace_id, (knowledge_base_id,)
        )
        snapshot = await service.submit(
            workspace_id=workspace.workspace_id,
            knowledge_base_id=scope[0],
            idempotency_key=idempotency_key,
            title=resolved_title,
            source_filename=filename,
            media_type=media_type,
            content=content,
        )
    except DocumentValidationError as error:
        raise HTTPException(
            status_code=_validation_status(error.code),
            detail={"code": error.code, "message": str(error)},
        ) from error
    except (InvalidKnowledgeBaseScopeError, InvalidIdempotencyKeyError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_ingestion_job", "message": str(error)},
        ) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "idempotency_conflict", "message": str(error)},
        ) from error
    except IngestionQueueUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ingestion_queue_unavailable", "message": str(error)},
        ) from error
    return _response(snapshot)


@router.get("/{job_id}", response_model=IngestionJobResponse)
async def get_ingestion_job(
    job_id: UUID,
    service: JobService,
    workspace: CurrentWorkspace,
) -> IngestionJobResponse:
    try:
        return _response(await service.get(workspace.workspace_id, job_id))
    except IngestionJobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ingestion_job_not_found", "message": str(error)},
        ) from error
