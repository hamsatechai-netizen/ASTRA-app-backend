"""
Base class every concrete service inherits from.

Not an `ABC` with abstract methods: the *shape* of a service (what use
cases it exposes) is inherently feature-specific, so there is no common
method contract to enforce here. What is common — depending on a
repository rather than a raw session — is captured by the constructor.
"""

from typing import Generic

from app.repositories.base import BaseRepository, ModelType


class BaseService(Generic[ModelType]):
    def __init__(self, repository: BaseRepository[ModelType]) -> None:
        self._repository = repository
