from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

from backend.db import async_engine
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import text

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    status: str
    timestamp: datetime
    version: str = "1.0.0"
    database: str
    uptime_seconds: float


class DetailedHealthStatus(HealthStatus):
    checks: Dict[str, Any]


# Store startup time for uptime calculation
startup_time = datetime.now(timezone.utc)


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Simple health check for load balancers/monitoring systems."""
    return {"status": "ok"}


@router.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    """Basic health check with database connectivity."""
    try:
        # Test database connection
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        db_status = "unhealthy"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )

    current_time = datetime.now(timezone.utc)
    uptime = (current_time - startup_time).total_seconds()

    return HealthStatus(
        status="healthy",
        timestamp=current_time,
        database=db_status,
        uptime_seconds=uptime,
    )


@router.get("/health/detailed", response_model=DetailedHealthStatus)
async def detailed_health() -> DetailedHealthStatus:
    """Detailed health check for debugging and monitoring."""
    checks = {}
    overall_status = "healthy"

    # Database check with timing
    try:
        start_time = asyncio.get_event_loop().time()
        async with async_engine.connect() as conn:
            result = await conn.execute(text("SELECT current_database(), version()"))
            row = result.fetchone()
        end_time = asyncio.get_event_loop().time()

        checks["database"] = {
            "status": "healthy",
            "response_time_ms": round((end_time - start_time) * 1000, 2),
            "database_name": row[0] if row else "unknown",
            "version": (row[1].split()[0:2] if row else "unknown"),  # First 2 words of version
        }
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "unhealthy"

    # Memory and system checks could go here in the future
    # For MVP, we'll keep it simple

    current_time = datetime.now(timezone.utc)
    uptime = (current_time - startup_time).total_seconds()

    return DetailedHealthStatus(
        status=overall_status,
        timestamp=current_time,
        database=checks["database"]["status"],
        uptime_seconds=uptime,
        checks=checks,
    )


__all__ = ["router"]
