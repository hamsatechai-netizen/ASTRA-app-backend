"""
Dashboard repository contract.

Backs the existing `hamsatech.athletes`, `hamsatech.sessions`, and
`hamsatech.shooting_session_log` tables. Kept as its own narrow interface
(same Interface Segregation rationale documented in
`app.modules.sessions.repositories.session_repository_interface`) rather
than reusing another module's repository for a different purpose.

Deliberately does NOT expose anything for streak, AI insights, or
Readiness/Recovery/Stress/Steady — none of those have a legitimate,
non-fabricated data source at the repository layer today (see
`app.modules.dashboard.services.dashboard_service` module docstring).
"""

from abc import ABC, abstractmethod
from datetime import datetime

from app.models.hamsatech_athlete import HamsaTechAthlete


class DashboardRepositoryInterface(ABC):
    """Abstract contract for resolving the athlete and reading their weekly training summary."""

    @abstractmethod
    async def get_athlete_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def count_completed_sessions_since(self, athlete_id: str, since: datetime) -> int:
        """Count `athlete_id`'s completed sessions (`end_time IS NOT NULL`) with `start_time >= since`."""

    @abstractmethod
    async def get_average_score_since(self, athlete_id: str, since: datetime) -> float | None:
        """
        Average `shooting_session_log.avg_score` across `athlete_id`'s completed sessions with
        `start_time >= since`. `None` if none of those sessions has a score row yet — never `0`,
        since a real average of nothing is not zero.
        """
