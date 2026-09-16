"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_documents import router as documents_router
from app.api.routes_export import router as export_router
from app.api.routes_misc import error_router, eval_router, sources_router
from app.api.routes_research import router as research_router
from app.core.config import get_settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ResearchForge API", version=settings.APP_VERSION,
                  description="Source-grounded AI research agent.", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.include_router(research_router)
    app.include_router(export_router)
    app.include_router(documents_router)
    app.include_router(sources_router)
    app.include_router(eval_router)
    app.include_router(error_router)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": settings.APP_VERSION,
                "mock_mode": settings.MOCK_MODE, "llm_provider": settings.LLM_PROVIDER,
                "search_provider": settings.SEARCH_PROVIDER}

    return app


app = create_app()
