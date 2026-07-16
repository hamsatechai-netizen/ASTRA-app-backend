"""
Service layer (application layer).

Services hold business/use-case orchestration and are the only layer API
routes are allowed to call. A service depends on one or more repository
*interfaces* (never on `AsyncSession` or ORM models directly), which keeps
business rules testable in isolation with fake/mock repositories.
"""
