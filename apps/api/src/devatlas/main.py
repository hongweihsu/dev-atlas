from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq.connections import RedisSettings, create_pool
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI

from devatlas.api.router import api_router
from devatlas.application.answer_documents import AnswerDocuments
from devatlas.application.answer_workspace_question import AnswerWorkspaceQuestion
from devatlas.application.corrective_answer_documents import CorrectiveAnswerDocuments
from devatlas.application.hybrid_retrieval import HybridChunkSearchRepository
from devatlas.application.ingest_document import IngestNewDocument
from devatlas.application.list_documents import ListDocuments
from devatlas.application.manage_conversations import ManageConversations
from devatlas.application.manage_document_lifecycle import ManageDocumentLifecycle
from devatlas.application.manage_document_versions import ManageDocumentVersions
from devatlas.application.manage_ingestion_jobs import ManageIngestionJobs
from devatlas.application.manage_knowledge_bases import ManageKnowledgeBases
from devatlas.application.run_agentic_research import RunAgenticResearch
from devatlas.application.search_documents import SearchDocuments
from devatlas.core.config import Settings, get_settings
from devatlas.core.tenancy import LEGACY_WORKSPACE_ID
from devatlas.infrastructure.authentication import (
    CognitoAccessTokenVerifier,
    CognitoIdentityTokenVerifier,
    DevelopmentSessionIssuer,
    OidcJwksTokenVerifier,
    PyJwtTokenVerifier,
)
from devatlas.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from devatlas.infrastructure.embedding import OpenAIEmbeddingProvider
from devatlas.infrastructure.extraction import OpenAIMultimodalDocumentExtractor
from devatlas.infrastructure.generation import (
    OpenAIAnswerGenerator,
    OpenAICorrectiveQueryGenerator,
    OpenAIQuestionContextualizer,
    OpenAIResearchAgent,
    OpenAIWorkspaceQuestionAnswerer,
)
from devatlas.infrastructure.observability import (
    HttpMetrics,
    RequestObservabilityMiddleware,
)
from devatlas.infrastructure.persistence import (
    SqlAlchemyBm25ChunkSearchRepository,
    SqlAlchemyChunkSearchRepository,
    SqlAlchemyConversationRepository,
    SqlAlchemyDocumentLifecycleRepository,
    SqlAlchemyDocumentListRepository,
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyIngestionJobRepository,
    SqlAlchemyIngestionUnitOfWorkFactory,
    SqlAlchemyKnowledgeBaseRepository,
    SqlAlchemyWorkspaceAccessRepository,
)
from devatlas.infrastructure.queue import ArqIngestionQueue


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    http_metrics = HttpMetrics.create()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(app_settings.database_url)
        session_factory = create_session_factory(engine)
        redis = await create_pool(RedisSettings.from_dsn(app_settings.redis_url))
        application.state.manage_ingestion_jobs = ManageIngestionJobs(
            repository=SqlAlchemyIngestionJobRepository(session_factory),
            queue=ArqIngestionQueue(redis),
        )
        application.state.list_documents = ListDocuments(
            SqlAlchemyDocumentListRepository(session_factory)
        )
        manage_knowledge_bases = ManageKnowledgeBases(
            SqlAlchemyKnowledgeBaseRepository(session_factory)
        )
        application.state.manage_knowledge_bases = manage_knowledge_bases
        application.state.manage_document_lifecycle = ManageDocumentLifecycle(
            SqlAlchemyDocumentLifecycleRepository(session_factory)
        )
        application.state.manage_document_versions = ManageDocumentVersions(
            SqlAlchemyDocumentVersionRepository(session_factory)
        )
        application.state.workspace_access_repository = (
            SqlAlchemyWorkspaceAccessRepository(session_factory)
        )
        if app_settings.auth_jwt_secret is not None:
            jwt_secret = app_settings.auth_jwt_secret.get_secret_value()
            application.state.token_verifier = PyJwtTokenVerifier(
                secret=jwt_secret,
                issuer=app_settings.auth_jwt_issuer,
                audience=app_settings.auth_jwt_audience,
            )
            if app_settings.auth_development_mode:
                application.state.development_session_issuer = DevelopmentSessionIssuer(
                    secret=jwt_secret,
                    issuer=app_settings.auth_jwt_issuer,
                    audience=app_settings.auth_jwt_audience,
                    subject="personal-owner",
                    workspace_id=LEGACY_WORKSPACE_ID,
                )
        elif app_settings.auth_jwks_url is not None:
            if app_settings.auth_cognito_client_id is not None:
                application.state.token_verifier = CognitoAccessTokenVerifier(
                    jwks_url=app_settings.auth_jwks_url,
                    issuer=app_settings.auth_jwt_issuer,
                    client_id=app_settings.auth_cognito_client_id,
                )
                application.state.identity_token_verifier = (
                    CognitoIdentityTokenVerifier(
                        jwks_url=app_settings.auth_jwks_url,
                        issuer=app_settings.auth_jwt_issuer,
                        client_id=app_settings.auth_cognito_client_id,
                    )
                )
            else:
                application.state.token_verifier = OidcJwksTokenVerifier(
                    jwks_url=app_settings.auth_jwks_url,
                    issuer=app_settings.auth_jwt_issuer,
                    audience=app_settings.auth_jwt_audience,
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
                document_extractor=OpenAIMultimodalDocumentExtractor(
                    client, model=app_settings.answer_model
                ),
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
            answer_documents = AnswerDocuments(
                search_documents=search_documents,
                generator=OpenAIAnswerGenerator(
                    client,
                    model=app_settings.answer_model,
                ),
            )
            application.state.answer_documents = answer_documents
            application.state.corrective_answer_documents = CorrectiveAnswerDocuments(
                answer_documents=answer_documents,
                query_generator=OpenAICorrectiveQueryGenerator(
                    client, model=app_settings.answer_model
                ),
            )
            application.state.manage_conversations = ManageConversations(
                repository=SqlAlchemyConversationRepository(session_factory),
                contextualizer=OpenAIQuestionContextualizer(
                    client, model=app_settings.answer_model
                ),
                answer_documents=answer_documents,
            )
            application.state.answer_workspace_question = AnswerWorkspaceQuestion(
                OpenAIWorkspaceQuestionAnswerer(
                    client,
                    manage_knowledge_bases,
                    model=app_settings.answer_model,
                )
            )
            application.state.run_agentic_research = RunAgenticResearch(
                OpenAIResearchAgent(
                    client,
                    knowledge_bases=manage_knowledge_bases,
                    search_documents=search_documents,
                    model=app_settings.answer_model,
                )
            )
        try:
            yield
        finally:
            del application.state.list_documents
            del application.state.manage_ingestion_jobs
            del application.state.manage_knowledge_bases
            del application.state.manage_document_lifecycle
            del application.state.manage_document_versions
            del application.state.workspace_access_repository
            if (
                app_settings.auth_jwt_secret is not None
                or app_settings.auth_jwks_url is not None
            ):
                del application.state.token_verifier
                if hasattr(application.state, "identity_token_verifier"):
                    del application.state.identity_token_verifier
                if app_settings.auth_development_mode:
                    del application.state.development_session_issuer
            if client is not None:
                del application.state.answer_workspace_question
                del application.state.run_agentic_research
                del application.state.manage_conversations
                del application.state.answer_documents
                del application.state.corrective_answer_documents
                del application.state.search_documents
                del application.state.ingest_new_document
                await client.close()
            await redis.aclose()
            await engine.dispose()

    application = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.http_metrics = http_metrics
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["DELETE", "GET", "POST"],
        allow_headers=["*"],
    )
    application.add_middleware(
        RequestObservabilityMiddleware,
        metrics=http_metrics,
    )
    application.include_router(api_router)
    return application


app = create_app()
