from fastapi import APIRouter

from devatlas.api.routes.documents import router as documents_router
from devatlas.api.routes.health import router as health_router
from devatlas.api.routes.search import router as search_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(documents_router)
api_router.include_router(search_router)
