"""
Declarative base for all ORM models.

A single shared `Base` is required so that Alembic's autogenerate
(`Base.metadata`) can see every model, and so every model participates in
the same mapper registry.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class every SQLAlchemy model must inherit from."""
