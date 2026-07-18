"""
Onboarding module.

Phase 1 status: Step 1 (Personal Details) only — see
`app.modules.onboarding.routers.onboarding_router`. Reads and updates the
existing, externally-owned `hamsatech.athletes` row for the authenticated
athlete (resolved via `app.modules.auth.dependencies.current_athlete`);
creates nothing and never touches `hamsatech.users` or the auth/OTP flow.

Submodules:
    constants/    Fixed values (allowed `Gender` values).
    schemas/      Request/response DTOs (OnboardingStep1Request, OnboardingStatusResponse).
    exceptions/   Onboarding-specific AppException subclasses.
    repositories/ Narrow repository contract over `hamsatech.athletes` for onboarding reads/writes.
    services/     `OnboardingService` — the Step 1 business logic.
    dependencies/ FastAPI DI providers.
    routers/      The versioned onboarding router, mounted under `/api/v2/onboarding`.
"""
