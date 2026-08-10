"""
Academies module.

Read-only listing of the existing, externally-owned `hamsatech.academies`
table — used by the Flutter onboarding client to populate the Step 2
academy picker (`academyId`). Requires authentication (the same
`get_current_athlete` dependency the onboarding module uses) but does
not otherwise touch or depend on the onboarding module.

Submodules:
    schemas/      Response DTO (`AcademyResponse`).
    repositories/ Narrow read-only repository contract over `hamsatech.academies`.
    services/     `AcademyService` — trivial pass-through to DTOs.
    dependencies/ FastAPI DI providers.
    routers/      The versioned academies router, mounted under `/api/v2/academies`.
"""
