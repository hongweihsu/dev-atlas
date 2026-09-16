from typing import Protocol

from devatlas.domain.document_ingestion import PreparedTextDocument


class DocumentExtractionUnavailableError(RuntimeError):
    """Raised when an external document extractor cannot complete a request."""


class DocumentExtractor(Protocol):
    async def prepare(
        self, *, content: bytes, source_filename: str, media_type: str
    ) -> PreparedTextDocument: ...
