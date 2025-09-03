from __future__ import annotations

from datetime import timedelta

import logfire
from backend.core.auth import create_access_token, generate_simple_user_id
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
async def get_access_token(request: TokenRequest) -> TokenResponse:
    """Get an access token for API usage.

    For MVP simplicity, this generates a token for any provided identifier.
    In a real production app, you'd validate credentials against a user database.
    """
    # For MVP: generate a simple user ID based on the identifier
    # In production, you'd look up the user in your database
    user_id = f"user_{abs(hash(request.identifier.lower().strip()))}"

    # Create token with 7-day expiration (adjust as needed)
    expires_delta = timedelta(days=7)
    access_token = create_access_token(user_id=user_id, expires_delta=expires_delta)

    logfire.info("Token generated", user_id=user_id, identifier=request.identifier)

    return TokenResponse(
        access_token=access_token,
        user_id=user_id,
        expires_in=int(expires_delta.total_seconds()),
    )


@router.post("/token/guest", response_model=TokenResponse)
async def get_guest_token() -> TokenResponse:
    """Get a guest token for anonymous usage.

    This is useful for users who want to try the API without providing any identifier.
    """
    user_id = generate_simple_user_id()

    # Guest tokens expire in 24 hours
    expires_delta = timedelta(hours=24)
    access_token = create_access_token(user_id=user_id, expires_delta=expires_delta)

    logfire.info("Guest token generated", user_id=user_id)

    return TokenResponse(
        access_token=access_token,
        user_id=user_id,
        expires_in=int(expires_delta.total_seconds()),
    )


__all__ = ["router"]
