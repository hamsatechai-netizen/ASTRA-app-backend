"""
Psychology Assessment module.

Serves the 25-question psychology assessment against the existing,
externally-owned `hamsatech` psychology schema (`psychology_questions`,
`psychology_question_options`, `psychology_responses`, `psychology_scores`,
`category_definitions`, `ai_insights`) — this module creates nothing;
progress is always derived live from `psychology_responses`, and scoring is
always delegated to the existing `hamsatech.calculate_psychology_scores` /
`hamsatech.generate_deterministic_insights` SQL functions, never
reimplemented in Python.

Submodules:
    schemas/      Request/response DTOs.
    exceptions/   Module-specific `AppException` subclasses.
    repositories/ Narrow repository contracts over the psychology tables
                   (catalog, responses, scoring), same Interface
                   Segregation pattern used by the onboarding module.
    services/     `PsychologyAssessmentService` — status, save-answer, and
                   complete business logic.
    dependencies/ FastAPI DI providers.
    routers/      The versioned router, mounted under
                   `/api/v2/psychology-assessment`.
"""
