"""
Auth repositories.

`OTPRepositoryInterface` / `OTPRepository` back this project's own
`otp_challenges` table. `UserRepositoryInterface` / `UserRepository` and
`AthleteProfileRepositoryInterface` / `AthleteProfileRepository` back the
existing, externally-owned `hamsatech.users` and `hamsatech.athletes`
tables respectively (see `app.models.hamsatech_user` /
`app.models.hamsatech_athlete` for why they use a separate, unmigrated
declarative base).
"""

from app.modules.auth.repositories.athlete_profile_repository import AthleteProfileRepository
from app.modules.auth.repositories.athlete_profile_repository_interface import (
    AthleteProfileRepositoryInterface,
)
from app.modules.auth.repositories.otp_repository import OTPRepository
from app.modules.auth.repositories.otp_repository_interface import OTPRepositoryInterface
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface

__all__ = [
    "OTPRepositoryInterface",
    "OTPRepository",
    "UserRepositoryInterface",
    "UserRepository",
    "AthleteProfileRepositoryInterface",
    "AthleteProfileRepository",
]
