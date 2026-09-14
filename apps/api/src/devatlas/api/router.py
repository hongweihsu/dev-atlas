from fastapi import APIRouter

from devatlas.api.routes.answers import router as answers_router
from devatlas.api.routes.authentication import router as authentication_router
from devatlas.api.routes.conversations import router as conversations_router
from devatlas.api.routes.documents import router as documents_router
from devatlas.api.routes.health import router as health_router
from devatlas.api.routes.ingestion_jobs import router as ingestion_jobs_router
from devatlas.api.routes.knowledge_bases import router as knowledge_bases_router
from devatlas.api.routes.search import router as search_router
from devatlas.api.routes.session import router as session_router
from devatlas.api.routes.workspace_questions import router as workspace_questions_router

api_router = APIRouter()
api_router.include_router(authentication_router)
api_router.include_router(conversations_router)
api_router.include_router(health_router)
api_router.include_router(ingestion_jobs_router)
api_router.include_router(knowledge_bases_router)
api_router.include_router(documents_router)
api_router.include_router(search_router)
api_router.include_router(answers_router)
api_router.include_router(session_router)
api_router.include_router(workspace_questions_router)
