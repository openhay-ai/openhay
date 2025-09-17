from __future__ import annotations

from datetime import datetime

from backend.core.auth import CurrentUser
from backend.db import AsyncSessionLocal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


class TotalCountResponse(BaseModel):
    count: int


class GroupCountItem(BaseModel):
    key: str
    count: int


class GroupCountResponse(BaseModel):
    items: list[GroupCountItem]


async def get_valid_time_range(
    start: datetime = Query(..., description="Start datetime (inclusive)"),
    end: datetime = Query(..., description="End datetime (exclusive)"),
) -> tuple[datetime, datetime]:
    if end <= start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'end' must be greater than 'start'",
        )
    return start, end


# Removed in-memory helpers; all aggregations are pushed to the database for
# performance and scalability.


@router.get("/total-messages", response_model=TotalCountResponse)
async def total_messages(
    current_user: CurrentUser,
    time_range: tuple[datetime, datetime] = Depends(get_valid_time_range),
) -> TotalCountResponse:
    start, end = time_range

    sql = text(
        """
        SELECT COUNT(*)::bigint AS total
        FROM conversation_message_run AS r,
             LATERAL jsonb_array_elements(r.messages) AS m,
             LATERAL jsonb_array_elements(
               COALESCE(m->'parts', '[]'::jsonb)
             ) AS p
        WHERE r.created_at >= :start
          AND r.created_at < :end
          AND p->>'part_kind' = 'user-prompt'
        """
    )
    async with AsyncSessionLocal() as session:
        result = await session.execute(sql, {"start": start, "end": end})
        total = result.scalar() or 0
    return TotalCountResponse(count=int(total))


@router.get("/messages-by-user", response_model=GroupCountResponse)
async def messages_by_user(
    current_user: CurrentUser,
    time_range: tuple[datetime, datetime] = Depends(get_valid_time_range),
) -> GroupCountResponse:
    start, end = time_range

    sql = text(
        """
        SELECT c.feature_params->>'user_id' AS user_id,
               COUNT(*)::bigint AS count
        FROM conversation_message_run AS r
        JOIN conversation AS c ON r.conversation_id = c.id,
             LATERAL jsonb_array_elements(r.messages) AS m,
             LATERAL jsonb_array_elements(
               COALESCE(m->'parts', '[]'::jsonb)
             ) AS p
        WHERE r.created_at >= :start
          AND r.created_at < :end
          AND p->>'part_kind' = 'user-prompt'
          AND c.feature_params->>'user_id' IS NOT NULL
        GROUP BY user_id
        ORDER BY count DESC, user_id ASC
        """
    )
    async with AsyncSessionLocal() as session:
        result = await session.execute(sql, {"start": start, "end": end})
        items = [GroupCountItem(key=str(r[0]), count=int(r[1])) for r in result.all()]
    return GroupCountResponse(items=items)


@router.get("/messages-by-preset", response_model=GroupCountResponse)
async def messages_by_preset(
    current_user: CurrentUser,
    time_range: tuple[datetime, datetime] = Depends(get_valid_time_range),
) -> GroupCountResponse:
    start, end = time_range

    sql = text(
        """
        SELECT f.key AS preset_key,
               COUNT(*)::bigint AS count
        FROM conversation_message_run AS r
        JOIN conversation AS c ON r.conversation_id = c.id
        JOIN feature_preset AS f ON f.id = c.feature_preset_id,
             LATERAL jsonb_array_elements(r.messages) AS m,
             LATERAL jsonb_array_elements(
               COALESCE(m->'parts', '[]'::jsonb)
             ) AS p
        WHERE r.created_at >= :start
          AND r.created_at < :end
          AND p->>'part_kind' = 'user-prompt'
        GROUP BY f.key
        ORDER BY count DESC, f.key ASC
        """
    )
    async with AsyncSessionLocal() as session:
        result = await session.execute(sql, {"start": start, "end": end})
        items = [GroupCountItem(key=str(r[0]), count=int(r[1])) for r in result.all()]
    return GroupCountResponse(items=items)


@router.get("/total-users", response_model=TotalCountResponse)
async def total_users(
    current_user: CurrentUser,
    time_range: tuple[datetime, datetime] = Depends(get_valid_time_range),
) -> TotalCountResponse:
    start, end = time_range

    sql = text(
        """
        SELECT COUNT(DISTINCT c.feature_params->>'user_id') AS cnt
        FROM conversation_message_run AS r
        JOIN conversation AS c ON r.conversation_id = c.id,
             LATERAL jsonb_array_elements(r.messages) AS m,
             LATERAL jsonb_array_elements(
               COALESCE(m->'parts', '[]'::jsonb)
             ) AS p
        WHERE r.created_at >= :start
          AND r.created_at < :end
          AND p->>'part_kind' = 'user-prompt'
          AND c.feature_params->>'user_id' IS NOT NULL
        """
    )
    async with AsyncSessionLocal() as session:
        result = await session.execute(sql, {"start": start, "end": end})
        count_val = result.scalar() or 0
    return TotalCountResponse(count=int(count_val))


__all__ = ["router"]
