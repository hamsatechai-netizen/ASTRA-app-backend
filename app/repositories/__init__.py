"""
Repository layer.

Repositories are the only layer allowed to speak SQLAlchemy/query syntax.
Services depend on repository *interfaces*, never on `AsyncSession`
directly, so persistence can be swapped or mocked without touching
business logic. `base.py` defines the generic CRUD contract every concrete
repository will implement.
"""
