"""
Pydantic schemas (request/response DTOs).

Kept separate from `app/models` (ORM) so the API contract can evolve
independently of the persistence schema. Empty aside from the shared base
in this phase — feature schemas arrive with their respective features.
"""
