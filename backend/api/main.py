from __future__ import annotations

from contextlib import asynccontextmanager

import logfire
from backend.api.routers.chat import router as chat_router
from backend.api.routers.featured import router as featured_router
from backend.api.routers.health import router as health_router
from backend.api.routers.research import router as research_router
from backend.api.routers.translate import router as translate_router
from backend.db import async_engine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text


def _get_cors_origins() -> list[str]:
    # Allow localhost dev ports by default; can be overridden by env in future
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*",  # keep permissive for local dev
    ]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify DB connectivity on startup; dispose engine on shutdown
    async with async_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    try:
        yield
    finally:
        await async_engine.dispose()


app = FastAPI(title="Open AI Hay API", lifespan=lifespan)

logfire.configure(scrubbing=False)
logfire.instrument_fastapi(app)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(featured_router)
app.include_router(research_router)
app.include_router(translate_router)


# Convenience for `uvicorn backend.api.main:app --reload`
__all__ = ["app"]
