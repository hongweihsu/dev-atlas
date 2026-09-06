from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from devatlas.api.router import api_router
from devatlas.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(api_router)
