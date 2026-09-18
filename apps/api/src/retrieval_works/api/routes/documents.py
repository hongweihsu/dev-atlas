from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel

from retrieval_works.api.dependencies.authentication import (
    CurrentWorkspace,
    WritableWorkspace,
)
from retrieval_works.api.routes.knowledge_bases import get_manage_knowledge_bases
from retrieval_works.application.ingest_document import (
    IngestNewDocument,
    IngestNewDocumentCommand,
    InvalidDocumentTitleError,
)
from retrieval_works.application.list_documents import ListDocuments
from retrieval_works.application.manage_document_lifecycle import (
    ManageDocumentLifecycle,
)
from retrieval_works.application.manage_document_versions import ManageDocumentVersions
from retrieval_works.application.ports.document_extraction import (
    DocumentExtractionUnavailableError,
)
from retrieval_works.application.ports.document_versions import (
    DocumentVersionNotFoundError,
)
from retrieval_works.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProviderUnavailableError,
)
from retrieval_works.application.ports.knowledge_bases import (
    InvalidKnowledgeBaseScopeError,
)
from retrieval_works.application.ports.persistence import (
    DocumentArchivedError,
    DocumentNotFoundError,
    DuplicateDocumentContentError,
)
from retrieval_works.domain.document_ingestion import (
    DEFAULT_MAX_UPLOAD_BYTES,
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
    archived_at: datetime | None
    knowledge_base_id: str
    knowledge_base_name: str


class DocumentVersionSummaryResponse(BaseModel):
    version_id: str
    version_number: int
    source_filename: str
    media_type: str
    content_checksum: str
    character_count: int
    chunk_count: int
    embedding_model: str
    embedding_dimension: int
    is_active: bool
    created_at: datetime


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


def get_manage_document_lifecycle(request: Request) -> ManageDocumentLifecycle:
    service = getattr(request.app.state, "manage_document_lifecycle", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "document_lifecycle_unavailable",
                "message": "document lifecycle management is not configured",
            },
        )
    return cast(ManageDocumentLifecycle, service)


DocumentLifecycleService = Annotated[
    ManageDocumentLifecycle, Depends(get_manage_document_lifecycle)
]


def get_manage_document_versions(request: Request) -> ManageDocumentVersions:
    service = getattr(request.app.state, "manage_document_versions", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "document_versions_unavailable",
                "message": "document version management is not configured",
            },
        )
    return cast(ManageDocumentVersions, service)


DocumentVersionService = Annotated[
    ManageDocumentVersions, Depends(get_manage_document_versions)
]


def _validation_status(code: DocumentValidationCode) -> int:
    if code is DocumentValidationCode.UNSUPPORTED_TYPE:
        return status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    if code is DocumentValidationCode.FILE_TOO_LARGE:
        return status.HTTP_413_CONTENT_TOO_LARGE
    return status.HTTP_422_UNPROCESSABLE_CONTENT


@router.get("", response_model=list[DocumentSummaryResponse])
async def list_documents(
    request: Request,
    service: DocumentListService,
    workspace: CurrentWorkspace,
    status_filter: Annotated[
        Literal["active", "archived"], Query(alias="status")
    ] = "active",
    knowledge_base_id: Annotated[UUID | None, Query()] = None,
) -> list[DocumentSummaryResponse]:
    try:
        scope = (
            await get_manage_knowledge_bases(request).resolve_scope(
                workspace.workspace_id, (knowledge_base_id,)
            )
            if knowledge_base_id is not None
            else ()
        )
        documents = await service.execute(
            workspace_id=workspace.workspace_id,
            status=status_filter,
            knowledge_base_ids=scope,
        )
    except InvalidKnowledgeBaseScopeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_knowledge_base_scope", "message": str(error)},
        ) from error
    return [
        DocumentSummaryResponse(
            document_id=str(document.document_id),
            title=document.title,
            active_version_id=str(document.active_version_id),
            active_version_number=document.active_version_number,
            source_filename=document.source_filename,
            chunk_count=document.chunk_count,
            updated_at=document.updated_at,
            archived_at=document.archived_at,
            knowledge_base_id=str(document.knowledge_base_id),
            knowledge_base_name=document.knowledge_base_name,
        )
        for document in documents
    ]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_document(
    document_id: UUID,
    service: DocumentLifecycleService,
    workspace: WritableWorkspace,
) -> None:
    try:
        await service.archive(workspace.workspace_id, document_id)
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "document_not_found", "message": str(error)},
        ) from error


@router.post("/{document_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
async def restore_document(
    document_id: UUID,
    service: DocumentLifecycleService,
    workspace: WritableWorkspace,
) -> None:
    try:
        await service.restore(workspace.workspace_id, document_id)
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "document_not_found", "message": str(error)},
        ) from error


@router.post(
    "", response_model=IngestDocumentResponse, status_code=status.HTTP_201_CREATED
)
async def ingest_document(
    request: Request,
    file: Annotated[UploadFile, File()],
    service: IngestionService,
    workspace: WritableWorkspace,
    title: Annotated[str, Form()] = "",
    knowledge_base_id: Annotated[UUID | None, Form()] = None,
) -> IngestDocumentResponse:
    scope: tuple[UUID, ...] = ()
    if knowledge_base_id is not None:
        try:
            scope = await get_manage_knowledge_bases(request).resolve_scope(
                workspace.workspace_id, (knowledge_base_id,)
            )
        except InvalidKnowledgeBaseScopeError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "invalid_knowledge_base_scope", "message": str(error)},
            ) from error
    return await _ingest(
        file=file,
        title=title,
        service=service,
        workspace_id=workspace.workspace_id,
        knowledge_base_id=scope[0] if scope else None,
    )


@router.post(
    "/{document_id}/versions",
    response_model=IngestDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_document_version(
    document_id: UUID,
    file: Annotated[UploadFile, File()],
    service: IngestionService,
    workspace: WritableWorkspace,
) -> IngestDocumentResponse:
    return await _ingest(
        file=file,
        title="",
        service=service,
        workspace_id=workspace.workspace_id,
        document_id=document_id,
    )


@router.get(
    "/{document_id}/versions", response_model=list[DocumentVersionSummaryResponse]
)
async def list_document_versions(
    document_id: UUID,
    service: DocumentVersionService,
    workspace: CurrentWorkspace,
) -> list[DocumentVersionSummaryResponse]:
    try:
        versions = await service.list_versions(workspace.workspace_id, document_id)
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "document_not_found", "message": str(error)},
        ) from error
    return [
        DocumentVersionSummaryResponse(
            version_id=str(version.version_id),
            version_number=version.version_number,
            source_filename=version.source_filename,
            media_type=version.media_type,
            content_checksum=version.content_checksum,
            character_count=version.character_count,
            chunk_count=version.chunk_count,
            embedding_model=version.embedding_model,
            embedding_dimension=version.embedding_dimension,
            is_active=version.is_active,
            created_at=version.created_at,
        )
        for version in versions
    ]


@router.post(
    "/{document_id}/versions/{version_id}/activate",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def activate_document_version(
    document_id: UUID,
    version_id: UUID,
    service: DocumentVersionService,
    workspace: WritableWorkspace,
) -> None:
    try:
        await service.activate_version(workspace.workspace_id, document_id, version_id)
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "document_not_found", "message": str(error)},
        ) from error
    except DocumentVersionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "document_version_not_found", "message": str(error)},
        ) from error
    except DocumentArchivedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "document_archived", "message": str(error)},
        ) from error


async def _ingest(
    *,
    file: UploadFile,
    title: str,
    service: IngestNewDocument,
    workspace_id: UUID,
    document_id: UUID | None = None,
    knowledge_base_id: UUID | None = None,
) -> IngestDocumentResponse:
    filename = file.filename or ""
    media_type = file.content_type or ""
    content = await file.read(DEFAULT_MAX_UPLOAD_BYTES + 1)
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
            knowledge_base_id=knowledge_base_id,
        )
        if document_id is None:
            result = await service.execute(workspace_id, command)
        else:
            result = await service.execute_version(workspace_id, document_id, command)
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
    except DocumentExtractionUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "document_extraction_unavailable", "message": str(error)},
        ) from error
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "document_not_found", "message": str(error)},
        ) from error
    except DocumentArchivedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "document_archived", "message": str(error)},
        ) from error
    except DuplicateDocumentContentError as error:
        detail: dict[str, str | bool] = {
            "code": "duplicate_document_content",
            "message": str(error),
        }
        if error.document_id is not None:
            detail["document_id"] = str(error.document_id)
            detail["document_archived"] = error.document_archived
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
