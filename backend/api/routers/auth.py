from __future__ import annotations

import hmac
from datetime import timedelta

import logfire
from backend.core.auth import (
    REFRESH_COOKIE_NAME,
    create_access_token,
    create_refresh_token,
    generate_simple_user_id,
    get_jwt_secret_key,
    verify_refresh_token,
)
from backend.settings import settings
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/auth", tags=["auth"])
SECURE_COOKIE = settings.env == "prod"
SAMESITE_VALUE = "none" if SECURE_COOKIE else "lax"


class TokenRequest(BaseModel):
    """Request model for getting an access token.

    For MVP, we'll use a simple approach where users can request a token
    with just an identifier (email, username, etc.) - no password required.
    """

    identifier: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Email, username, or any unique identifier",
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user_id: str


@router.post("/token", response_model=TokenResponse)
async def get_access_token(request: TokenRequest, response: Response) -> TokenResponse:
    """Get an access token for API usage.

    For MVP simplicity, this generates a token for any provided identifier.
    In a real production app, you'd validate credentials against a user database.
    """
    # For MVP: generate a secure but deterministic user ID
    # In production, you'd look up the user in your database
    # Using HMAC to make it non-enumerable but consistent per identifier
    identifier_normalized = request.identifier.lower().strip()
    user_hash = hmac.new(
        get_jwt_secret_key().encode(),
        identifier_normalized.encode(),
        digestmod="sha256",
    ).hexdigest()[:16]
    user_id = f"user_{user_hash}"

    # Create token with configured expiration
    expires_delta = timedelta(days=settings.access_token_expire_days)
    access_token = create_access_token(user_id=user_id, expires_delta=expires_delta)
    # Issue refresh cookie (30d)
    refresh_token = create_refresh_token(user_id=user_id)
    # Cookie flags: httpOnly, secure (recommend prod), sameSite strict
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=SECURE_COOKIE,
        samesite=SAMESITE_VALUE,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )

    logfire.info("Token generated", user_id=user_id, identifier=request.identifier)

    return TokenResponse(
        access_token=access_token,
        user_id=user_id,
        expires_in=int(expires_delta.total_seconds()),
    )


@router.post("/token/guest", response_model=TokenResponse)
async def get_guest_token(response: Response) -> TokenResponse:
    """Get a guest token for anonymous usage.

    This is useful for users who want to try the API without providing any identifier.
    """
    user_id = generate_simple_user_id()

    # Guest tokens expire based on configuration
    expires_delta = timedelta(hours=settings.guest_token_expire_hours)
    access_token = create_access_token(user_id=user_id, expires_delta=expires_delta)
    refresh_token = create_refresh_token(user_id=user_id)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=SECURE_COOKIE,
        samesite=SAMESITE_VALUE,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )

    logfire.info("Guest token generated", user_id=user_id)

    return TokenResponse(
        access_token=access_token,
        user_id=user_id,
        expires_in=int(expires_delta.total_seconds()),
    )


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_access_token(request: Request, response: Response) -> RefreshResponse:
    """Rotate access token using refresh cookie."""
    token_val = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token_val:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    data = verify_refresh_token(token_val)
    # New short-lived access token
    expires_delta = timedelta(days=settings.access_token_expire_days)
    access_token = create_access_token(user_id=data.user_id, expires_delta=expires_delta)
    # Rotate refresh token, update cookie
    new_refresh = create_refresh_token(user_id=data.user_id)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=new_refresh,
        httponly=True,
        secure=SECURE_COOKIE,
        samesite=SAMESITE_VALUE,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )
    return RefreshResponse(
        access_token=access_token,
        user_id=data.user_id,
        expires_in=int(expires_delta.total_seconds()),
    )


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/")
    return {"status": "ok"}


__all__ = ["router"]
