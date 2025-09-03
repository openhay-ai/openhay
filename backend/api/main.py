from __future__ import annotations

from contextlib import asynccontextmanager

import logfire
from backend.api.routers.chat import router as chat_router
from backend.api.routers.contact import router as contact_router
from backend.api.routers.featured import router as featured_router
from backend.api.routers.health import router as health_router
from backend.api.routers.research import router as research_router
from backend.api.routers.translate import router as translate_router
from backend.db import async_engine, create_all, seed_feature_presets
from backend.settings import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text


def _get_cors_origins() -> list[str]:
    # Allow localhost dev ports by default
    # Avoid '*' when allow_credentials is True
    origins: list[str] = []
    # Add Railway public domain if provided
    railway_domain = settings.railway_public_domain
    if railway_domain:
        origins.append(f"https://{railway_domain}")
    # Add explicit HOST_URL if provided
    host_url = settings.host_url
    if host_url:
        origins.append(host_url)
    # Optional comma-separated ALLOWED_ORIGINS env
    extra = settings.allowed_origins
    if extra:
        for item in extra.split(","):
            val = item.strip()
            if val:
                origins.append(val)
    # De-duplicate while preserving order
    seen = set()
    unique: list[str] = []
    for o in origins:
        if o not in seen:
            unique.append(o)
            seen.add(o)
    return unique


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify DB connectivity on startup; dispose engine on shutdown
    async with async_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    # Ensure database schema and seeds are initialized (idempotent)
    await create_all()
    await seed_feature_presets()
    try:
        yield
    finally:
        await async_engine.dispose()


app = FastAPI(title="Open AI Hay API", lifespan=lifespan)

logfire.configure(token=settings.logfire_token, scrubbing=False)
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
app.include_router(contact_router)


# Convenience for `uvicorn backend.api.main:app --reload`
__all__ = ["app"]
