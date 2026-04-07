from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.health import router as health_router
from app.api.query import router as query_router
from app.api.trigger import router as trigger_router
from app.api.callback import router as callback_router
from app.api.callback_compat import router as callback_compat_router
from app.api.search import router as search_router
from app.api.dashboard import router as dashboard_router
from app.api.auth import router as auth_router
from app.services.auth_service import ensure_auth_schema
from app.services.search_center import bootstrap_search_runtime

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(query_router, prefix=settings.api_prefix)
app.include_router(trigger_router, prefix=settings.api_prefix)
app.include_router(callback_router, prefix=settings.api_prefix)
app.include_router(callback_compat_router, prefix=settings.api_prefix)
app.include_router(search_router, prefix=settings.api_prefix)
app.include_router(dashboard_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)


@app.on_event("startup")
def _startup_bootstrap() -> None:
    ensure_auth_schema()
    bootstrap_search_runtime()
