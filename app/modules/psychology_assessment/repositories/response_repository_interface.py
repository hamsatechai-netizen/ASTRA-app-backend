"""
Psychology-response repository contract.

Backs the existing `hamsatech.athletes` table (for athlete resolution —
same table, same `get_by_contact_number` shape as
`OnboardingRepositoryInterface`, kept as its own narrow interface per the
Interface Segregation rationale already used throughout this project) and
the existing `hamsatech.psychology_responses` table (one row per saved
answer). No unique constraint exists on `(athlete_id, question_id)` on the
real table, so `create` must only ever be called once no such row exists
yet for that athlete/question pair; `update` only ever touches an existing
row's `chosen_option` / `answer_text`.

`acquire_answer_lock` guards the check-then-act span between reading and
writing that row against a concurrent double-submit for the same
athlete/question (e.g. a fast double-tap of "Next") — same
transaction-scoped `pg_advisory_xact_lock` pattern as
`AthleteProfileRepository._generate_next_athlete_id`, keyed per
athlete/question instead of globally.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.models.hamsatech_athlete import HamsaTechAthlete
from app.models.hamsatech_psychology import HamsaTechPsychologyResponse


class PsychologyResponseRepositoryInterface(ABC):
    """Abstract contract for resolving the athlete and reading/writing their assessment answers."""

    @abstractmethod
    async def get_by_contact_number(self, phone_number: str) -> HamsaTechAthlete | None:
        """Return the athlete profile whose `contact_number` matches `phone_number`, if any."""

    @abstractmethod
    async def get_answered_question_numbers(self, athlete_id: str) -> set[int]:
        """Return the set of `question_number`s `athlete_id` has already answered."""

    @abstractmethod
    async def acquire_answer_lock(self, athlete_id: str, question_number: int) -> None:
        """
        Acquire a transaction-scoped Postgres advisory lock keyed on
        `(athlete_id, question_number)`, blocking until any other
        concurrent transaction holding the same lock commits or rolls
        back. Must be called before `get_by_athlete_and_question` in the
        save-answer flow so two simultaneous requests for the same
        athlete/question can never both observe "no existing row" and
        both `create`.
        """

    @abstractmethod
    async def get_by_athlete_and_question(
        self, athlete_id: str, question_number: int
    ) -> HamsaTechPsychologyResponse | None:
        """Return `athlete_id`'s existing response to `question_number`, if any."""

    @abstractmethod
    async def create(
        self, athlete_id: str, question_number: int, option_code: str, answer_text: str | None
    ) -> HamsaTechPsychologyResponse:
        """Insert a new response row. Only called when no row exists yet for this athlete/question."""

    @abstractmethod
    async def update(
        self, response: HamsaTechPsychologyResponse, option_code: str, answer_text: str | None
    ) -> HamsaTechPsychologyResponse:
        """Update `chosen_option` / `answer_text` on an existing `response` row."""

    @abstractmethod
    async def get_all_for_athlete(self, athlete_id: str) -> Sequence[HamsaTechPsychologyResponse]:
        """Return every response row saved by `athlete_id`."""
