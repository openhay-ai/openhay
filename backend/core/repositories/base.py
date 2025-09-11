from __future__ import annotations

from typing import Generic, Iterable, Optional, Sequence, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

TModel = TypeVar("TModel", bound=SQLModel)


class BaseRepository(Generic[TModel]):
    """Generic base repository for SQLModel entities.

    Provides simple CRUD helpers. Concrete repositories should extend this
    class and specify the model type and any domain-specific queries.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, entity: TModel) -> TModel:
        self.session.add(entity)
        return entity

    async def add_all(self, entities: Iterable[TModel]) -> Sequence[TModel]:
        self.session.add_all(list(entities))
        return list(entities)

    async def get(self, model_type: type[TModel], id_: object) -> Optional[TModel]:
        return await self.session.get(model_type, id_)

    async def list(self, model_type: type[TModel]) -> list[TModel]:
        result = await self.session.execute(select(model_type))
        return list(result.scalars().all())

    async def delete(self, entity: TModel) -> None:
        await self.session.delete(entity)

    async def commit(self) -> None:
        await self.session.commit()

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, entity: TModel) -> TModel:
        await self.session.refresh(entity)
        return entity
