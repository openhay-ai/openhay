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
REFRESH_COOKIE_NAME = "refresh_token"


class TokenData(BaseModel):
    user_id: str
    exp: datetime


class AuthUser(BaseModel):
    user_id: str
    is_authenticated: bool = True


def get_jwt_secret_key() -> str:
    """Get JWT secret key from environment or use default for development."""
    if settings.jwt_secret_key is None:
        # In production, always set JWT_SECRET_KEY environment variable
        if settings.env == "prod":
            raise RuntimeError("JWT_SECRET_KEY must be configured in production environment")
        # Development fallback with warning
        import warnings

        warnings.warn(
            "Using insecure default JWT secret for development. "
            "Set JWT_SECRET_KEY environment variable.",
            UserWarning,
        )
        return "dev-secret-key-change-in-production"

    return settings.jwt_secret_key


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default expiration from settings
        expire = datetime.now(timezone.utc) + timedelta(days=settings.access_token_expire_days)

    to_encode = {
        "user_id": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "token_type": "access",
    }

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


# Refresh token helpers
def create_refresh_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token. Longer-lived; only used to mint access tokens."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default refresh lifetime from settings
        expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    claims = {
        "user_id": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "token_type": "refresh",
    }
    return jwt.encode(claims, get_jwt_secret_key(), algorithm=ALGORITHM)


def verify_refresh_token(token: str) -> TokenData:
    """Verify a refresh token and return token data; enforces token_type == refresh."""
    try:
        payload = jwt.decode(token, get_jwt_secret_key(), algorithms=[ALGORITHM])
        if payload.get("token_type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id: str = payload.get("user_id")
        if not user_id:
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
            detail="Refresh token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate refresh token",
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
