from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import jwt
from backend.settings import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# JWT Configuration
ALGORITHM = "HS256"
# Generate a secure secret key - you should set this in your environment
DEFAULT_SECRET_KEY = "your-secret-key-change-this-in-production"


class TokenData(BaseModel):
    user_id: str
    exp: datetime


class AuthUser(BaseModel):
    user_id: str
    is_authenticated: bool = True


def get_jwt_secret_key() -> str:
    """Get JWT secret key from environment or use default for development."""
    # In production, always set JWT_SECRET_KEY environment variable
    return getattr(settings, "jwt_secret_key", None) or DEFAULT_SECRET_KEY


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default: 7 days for MVP (you can adjust this)
        expire = datetime.now(timezone.utc) + timedelta(days=7)

    to_encode = {"user_id": user_id, "exp": expire, "iat": datetime.now(timezone.utc)}

    encoded_jwt = jwt.encode(to_encode, get_jwt_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> TokenData:
    """Verify and decode JWT token."""
    try:
        payload = jwt.decode(token, get_jwt_secret_key(), algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user_id",
                headers={"WWW-Authenticate": "Bearer"},
            )

        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing expiration",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return TokenData(user_id=user_id, exp=exp_datetime)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Security scheme
security = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> AuthUser:
    """Extract and validate JWT token from request."""
    token_data = verify_token(credentials.credentials)
    return AuthUser(user_id=token_data.user_id)


# Optional auth dependency (for endpoints that work with or without auth)
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> Optional[AuthUser]:
    """Optional authentication - returns None if no valid token."""
    if not credentials:
        return None
    try:
        token_data = verify_token(credentials.credentials)
        return AuthUser(user_id=token_data.user_id)
    except HTTPException:
        return None


def generate_simple_user_id() -> str:
    """Generate a simple user ID for MVP (you might want to use UUIDs in production)."""
    return f"user_{secrets.token_urlsafe(16)}"


# Type aliases for convenience
CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
OptionalUser = Annotated[Optional[AuthUser], Depends(get_current_user_optional)]
