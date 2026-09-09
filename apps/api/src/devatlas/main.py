from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI

from devatlas.api.router import api_router
from devatlas.application.answer_documents import AnswerDocuments
from devatlas.application.hybrid_retrieval import HybridChunkSearchRepository
from devatlas.application.ingest_document import IngestNewDocument
from devatlas.application.list_documents import ListDocuments
from devatlas.application.search_documents import SearchDocuments
from devatlas.core.config import Settings, get_settings
from devatlas.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from devatlas.infrastructure.embedding import OpenAIEmbeddingProvider
from devatlas.infrastructure.generation import OpenAIAnswerGenerator
from devatlas.infrastructure.persistence import (
    SqlAlchemyBm25ChunkSearchRepository,
    SqlAlchemyChunkSearchRepository,
    SqlAlchemyDocumentListRepository,
    SqlAlchemyIngestionUnitOfWorkFactory,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(app_settings.database_url)
        session_factory = create_session_factory(engine)
        application.state.list_documents = ListDocuments(
            SqlAlchemyDocumentListRepository(session_factory)
        )
        client: AsyncOpenAI | None = None
        if app_settings.openai_api_key is not None:
            client = AsyncOpenAI(
                api_key=app_settings.openai_api_key.get_secret_value(),
            )
            provider = OpenAIEmbeddingProvider(
                client,
                model=app_settings.embedding_model,
                dimension=app_settings.embedding_dimension,
            )
            application.state.ingest_new_document = IngestNewDocument(
                embedding_provider=provider,
                unit_of_work_factory=SqlAlchemyIngestionUnitOfWorkFactory(
                    session_factory
                ),
                expected_embedding_dimension=app_settings.embedding_dimension,
            )
            search_documents = SearchDocuments(
                embedding_provider=provider,
                repository=HybridChunkSearchRepository(
                    vector=SqlAlchemyChunkSearchRepository(session_factory),
                    lexical=SqlAlchemyBm25ChunkSearchRepository(session_factory),
                ),
            )
            application.state.search_documents = search_documents
            application.state.answer_documents = AnswerDocuments(
                search_documents=search_documents,
                generator=OpenAIAnswerGenerator(
                    client,
                    model=app_settings.answer_model,
                ),
            )
        try:
            yield
        finally:
            del application.state.list_documents
            if client is not None:
                del application.state.answer_documents
                del application.state.search_documents
                del application.state.ingest_new_document
                await client.close()
            await engine.dispose()

    application = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    return application


app = create_app()
