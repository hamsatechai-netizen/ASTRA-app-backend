"""Request DTOs for the baseline module."""

from pydantic import Field

from app.schemas.base import BaseSchema


class SaveBaselineRequest(BaseSchema):
    """
    Request body for `POST /api/mobile/athletes/{athlete_id}/baseline`.

    Matches exactly what the existing, active Flutter client already sends
    (`ApiService.saveBaselineHR`, hamsatech_app
    `lib/core/services/api_service.dart:1038-1047`) — no field was added,
    renamed, or removed to fit this schema. `athlete_id` comes from the
    URL path (not the body), matching the existing Flutter call shape.

    The bound below is a basic sanity check, not a specific clinical
    threshold: it exists only to reject obviously-garbage input (zero,
    negative, or absurdly large values), not to encode a medical opinion
    about valid resting heart rate.
    """

    resting_hr: int = Field(..., gt=0, le=300, description="Captured resting heart rate, in BPM.")
