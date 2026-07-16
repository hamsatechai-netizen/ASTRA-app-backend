"""
Generic repository contract (Repository Pattern).

`BaseRepository[ModelType]` is an abstract base — it defines *what* every
concrete repository must support, not *how*. Concrete repositories (added
alongside their models in later phases) implement these methods against a
specific `AsyncSession` + ORM model, keeping query logic out of services.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType")


class BaseRepository(ABC, Generic[ModelType]):
    def __init__(self, session: AsyncSession, model: type[ModelType]) -> None:
        self._session = session
        self._model = model

    @abstractmethod
    async def get_by_id(self, id_: UUID) -> ModelType | None: ...

    @abstractmethod
    async def list(self, *, offset: int = 0, limit: int = 100) -> Sequence[ModelType]: ...

    @abstractmethod
    async def create(self, entity: ModelType) -> ModelType: ...

    @abstractmethod
    async def update(self, entity: ModelType) -> ModelType: ...

    @abstractmethod
    async def delete(self, entity: ModelType) -> None: ...
