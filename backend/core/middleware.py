from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Callable, Dict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Don't cache sensitive endpoints
        sensitive_paths = ("/api/chat", "/api/research", "/api/translate")
        if request.url.path.startswith(sensitive_paths):
            cache_control = "no-store, no-cache, must-revalidate, proxy-revalidate"
            response.headers["Cache-Control"] = cache_control
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size to prevent abuse."""

    def __init__(self, app, max_size: int = 10 * 1024 * 1024):  # 10MB
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check content-length header if present
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Request body too large",
                    "max_size_mb": self.max_size // (1024 * 1024),
                },
            )

        return await call_next(request)


# Simple in-memory rate limiter for basic protection
class SimpleRateLimiter:
    """Simple in-memory rate limiter using sliding window."""

    def __init__(self):
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        async with self.lock:
            now = time.time()
            window_start = now - window_seconds

            # Clean old requests
            while self.requests[key] and self.requests[key][0] <= window_start:
                self.requests[key].popleft()

            # Check if limit exceeded
            if len(self.requests[key]) >= max_requests:
                return False

            # Record this request
            self.requests[key].append(now)
            return True


# Global rate limiter instance
rate_limiter = SimpleRateLimiter()


class APIRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for API endpoints."""

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks and auth endpoints
        skip_paths = ["/healthz", "/api/auth/token", "/api/auth/token/guest"]
        if request.url.path in skip_paths:
            return await call_next(request)

        # Extract client identifier (IP address for now)
        client_ip = get_remote_address(request)

        # Different rate limits for different endpoints
        rate_limits = {
            "/api/chat": (20, 60),  # 20 requests per minute
            "/api/research": (10, 60),  # 10 requests per minute (expensive)
            "/api/translate": (30, 60),  # 30 requests per minute
            "default": (50, 60),  # 50 requests per minute for other endpoints
        }

        # Find matching rate limit
        max_requests, window = rate_limits.get("default")
        for path, (max_req, win) in rate_limits.items():
            if path != "default" and request.url.path.startswith(path):
                max_requests, window = max_req, win
                break

        # Create rate limit key
        path_parts = request.url.path.split("/")[1:3]
        rate_key = f"{client_ip}:{path_parts}"

        # Check rate limit
        if not await rate_limiter.is_allowed(rate_key, max_requests, window):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "max_requests": max_requests,
                    "window_seconds": window,
                    "retry_after": window,
                },
                headers={"Retry-After": str(window)},
            )

        return await call_next(request)


# Alternative using slowapi for more sophisticated rate limiting
def create_limiter() -> Limiter:
    """Create a slowapi limiter instance."""
    return Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": f"Rate limit exceeded: {exc.detail}",
            "retry_after": getattr(exc, "retry_after", 60),
        },
        headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
    )


__all__ = [
    "SecurityHeadersMiddleware",
    "RequestSizeLimitMiddleware",
    "APIRateLimitMiddleware",
    "create_limiter",
    "rate_limit_exceeded_handler",
]
