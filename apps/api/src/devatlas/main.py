from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI

from devatlas.api.router import api_router
from devatlas.application.ingest_document import IngestNewDocument
from devatlas.core.config import Settings, get_settings
from devatlas.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from devatlas.infrastructure.embedding import OpenAIEmbeddingProvider
from devatlas.infrastructure.persistence import SqlAlchemyIngestionUnitOfWorkFactory


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if app_settings.openai_api_key is None:
            yield
            return

        engine = create_database_engine(app_settings.database_url)
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
                create_session_factory(engine)
            ),
            expected_embedding_dimension=app_settings.embedding_dimension,
        )
        try:
            yield
        finally:
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
