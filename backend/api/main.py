from __future__ import annotations

import logfire
from backend.api.routers.chat import router as chat_router
from backend.api.routers.featured import router as featured_router
from backend.api.routers.health import router as health_router
from backend.api.routers.research import router as research_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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


app = FastAPI(title="Open AI Hay API")

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


# Convenience for `uvicorn backend.api.main:app --reload`
__all__ = ["app"]
