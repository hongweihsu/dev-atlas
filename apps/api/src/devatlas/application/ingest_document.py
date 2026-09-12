from dataclasses import dataclass
from uuid import UUID, uuid4

from devatlas.application.ports.embedding import (
    EmbeddingProvider,
    validate_embedding_batch,
)
from devatlas.application.ports.persistence import (
    IngestionUnitOfWorkFactory,
    NewChunkRecord,
    NewDocumentRecord,
    NewDocumentVersionRecord,
    chunk_embeddings,
)
from devatlas.domain.document_ingestion import prepare_text_document
from devatlas.domain.text_processing import chunk_text


@dataclass(frozen=True, slots=True)
class IngestNewDocumentCommand:
    title: str
    source_filename: str
    media_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class IngestedDocument:
    document_id: UUID
    version_id: UUID
    checksum: str
    chunk_count: int
    version_number: int


class InvalidDocumentTitleError(ValueError):
    """Raised when a document title violates the ingestion contract."""


class IngestNewDocument:
    """Prepare, embed, and atomically persist a new document and Version 1."""

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        unit_of_work_factory: IngestionUnitOfWorkFactory,
        expected_embedding_dimension: int = 1536,
    ) -> None:
        if embedding_provider.dimension != expected_embedding_dimension:
            raise ValueError(
                f"provider dimension {embedding_provider.dimension} does not match "
                f"configured dimension {expected_embedding_dimension}"
            )
        self._embedding_provider = embedding_provider
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self, workspace_id: UUID, command: IngestNewDocumentCommand
    ) -> IngestedDocument:
        title = command.title.strip()
        if not title:
            raise InvalidDocumentTitleError("title must not be empty")
        if len(title) > 255:
            raise InvalidDocumentTitleError("title must not exceed 255 characters")

        document_id = uuid4()
        record = await self._prepare_record(
            command,
            document_id=document_id,
            title=title,
        )
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.documents.add(workspace_id, record)
            await unit_of_work.commit()

        return self._result(record, version_number=1)

    async def execute_version(
        self,
        workspace_id: UUID,
        document_id: UUID,
        command: IngestNewDocumentCommand,
    ) -> IngestedDocument:
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.documents.ensure_version_target(
                workspace_id, document_id
            )
        record = await self._prepare_record(
            command,
            document_id=document_id,
            title="",
        )
        async with self._unit_of_work_factory() as unit_of_work:
            version_number = await unit_of_work.documents.add_version(
                workspace_id,
                document_id,
                record.version,
            )
            await unit_of_work.commit()

        return self._result(record, version_number=version_number)

    async def _prepare_record(
        self,
        command: IngestNewDocumentCommand,
        *,
        document_id: UUID,
        title: str,
    ) -> NewDocumentRecord:
        prepared = prepare_text_document(
            content=command.content,
            source_filename=command.source_filename,
            media_type=command.media_type,
        )
        chunks = chunk_text(prepared.normalized_text)
        embeddings = await self._embedding_provider.embed(
            [chunk.text for chunk in chunks]
        )
        validate_embedding_batch(
            embeddings,
            expected_count=len(chunks),
            expected_dimension=self._embedding_provider.dimension,
        )
        frozen_embeddings = chunk_embeddings(embeddings)

        version_id = uuid4()
        return NewDocumentRecord(
            id=document_id,
            title=title,
            version=NewDocumentVersionRecord(
                id=version_id,
                version_number=1,
                source_filename=prepared.source_filename,
                media_type=prepared.media_type,
                content_checksum=prepared.content_checksum,
                normalized_text=prepared.normalized_text,
                byte_size=prepared.byte_size,
                character_count=prepared.character_count,
                is_active=True,
                embedding_model=self._embedding_provider.model,
                embedding_dimension=self._embedding_provider.dimension,
                chunks=tuple(
                    NewChunkRecord(
                        id=uuid4(),
                        ordinal=chunk.ordinal,
                        text=chunk.text,
                        start_offset=chunk.start_offset,
                        end_offset=chunk.end_offset,
                        embedding=embedding,
                    )
                    for chunk, embedding in zip(
                        chunks,
                        frozen_embeddings,
                        strict=True,
                    )
                ),
            ),
        )

    @staticmethod
    def _result(
        record: NewDocumentRecord,
        *,
        version_number: int,
    ) -> IngestedDocument:
        return IngestedDocument(
            document_id=record.id,
            version_id=record.version.id,
            checksum=record.version.content_checksum,
            chunk_count=len(record.version.chunks),
            version_number=version_number,
        )
