"""
Declarative base for models mapping onto tables this project does not
own or migrate.

Deliberately a *separate* registry from `app.database.base.Base`: models
here participate in ordinary SQLAlchemy ORM queries (select/insert/update)
through the same engine and sessions, but are structurally invisible to
Alembic's autogenerate (`target_metadata = Base.metadata` in
`migrations/env.py` only ever sees `Base`'s registry) — so a future
`alembic revision --autogenerate` can never propose creating, altering,
or dropping a table it doesn't fully model, no matter what gets imported
where else. Use this for tables owned by another system (e.g.
`hamsatech.*`); use `Base` (`app.database.base`) for tables this project
creates and migrates itself.
"""

from sqlalchemy.orm import DeclarativeBase


class ExternalBase(DeclarativeBase):
    """Base class for ORM models mapping onto externally-owned tables never migrated by this project."""
