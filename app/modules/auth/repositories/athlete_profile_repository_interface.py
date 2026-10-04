"""
Athlete-profile repository contract.

Backs the existing `hamsatech.athletes` table (see
`app.models.hamsatech_athlete`). This backend only ever checks for and
creates a minimal row keyed by `contact_number`, to resolve onboarding
status — it has no visibility into or responsibility for the rest of
that table's 17 columns, which are owned entirely by other systems.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.hamsatech_athlete import HamsaTechAthlete


@dataclass(frozen=True, slots=True)
class AthleteContactMatch:
    """
    Outcome of resolving an athlete profile by `contact_number` — three
    states, never conflated into one nullable return value:

    - `athlete` set, `is_ambiguous` False: exactly one profile matched.
    - `athlete` is `None`, `is_ambiguous` False: no profile matched.
    - `athlete` is `None`, `is_ambiguous` True: two or more profiles share
      this phone number (see the Blocker B investigation — no unique
      constraint exists on `contact_number`). Deterministic and safe:
      never guesses which of the ambiguous rows is "the" athlete, and
      never raises for this case — see `AthleteProfileRepository
      .get_by_contact_number` for the failure this replaced
      (`scalar_one_or_none()` raising `MultipleResultsFound`, an unhandled
      500 for the whole login request).
    """

    athlete: HamsaTechAthlete | None
    is_ambiguous: bool


class AthleteProfileRepositoryInterface(ABC):
    """Abstract contract for reading and minimally creating athlete profiles."""

    @abstractmethod
    async def get_by_contact_number(self, phone_number: str) -> AthleteContactMatch:
        """
        Resolve the athlete profile(s) whose `contact_number` matches
        `phone_number`. Must never raise on more than one match — see
        `AthleteContactMatch` for the three states this returns instead.
        """

    @abstractmethod
    async def create_minimal(self, phone_number: str) -> HamsaTechAthlete:
        """Create a new athlete profile with `contact_number` set to `phone_number`."""

    async def count_by_contact_number(self, phone_number: str) -> int:
        """
        Return how many `athletes` rows have `contact_number == phone_number`.

        Largely redundant with `get_by_contact_number`'s own `is_ambiguous`
        flag now that it, too, safely detects duplicates — but deliberately
        kept as an independent, defense-in-depth check inside
        `UserService`'s returning-athlete uid self-heal (see its docstring):
        the uid-linking write is gated on its OWN fresh re-check, not solely
        on a flag computed earlier in the same request, so a future change
        to `get_by_contact_number` that weakened its own guard would not by
        itself make an unsafe link possible.

        Deliberately concrete, not `@abstractmethod` — same established
        pattern as `UserRepositoryInterface.set_uid_if_absent` / `get_by_uid`.
        The one existing fake of this interface
        (`test_verify_otp.FakeAthleteProfileRepository`) stores at most one
        athlete per phone number in its dict, so `1` (assume unambiguous) is
        already the correct default for it; only the real, SQLAlchemy-backed
        `AthleteProfileRepository` needs a real count.
        """
        return 1
