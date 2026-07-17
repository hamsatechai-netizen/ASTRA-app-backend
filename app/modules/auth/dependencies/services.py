"""
Service/repository/provider construction for FastAPI's DI system.

Each function is a `Depends()`-compatible provider; chaining them (as
`get_otp_service`, `get_user_service`, and `get_auth_service` do) is how
the router ends up with a fully-wired `AuthService` per request without
constructing anything itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.auth.providers.sms_provider import SMSProviderInterface
from app.modules.auth.providers.twilio_sms_provider import TwilioSMSProvider
from app.modules.auth.repositories.athlete_profile_repository import AthleteProfileRepository
from app.modules.auth.repositories.athlete_profile_repository_interface import (
    AthleteProfileRepositoryInterface,
)
from app.modules.auth.repositories.otp_repository import OTPRepository
from app.modules.auth.repositories.otp_repository_interface import OTPRepositoryInterface
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.repositories.user_repository_interface import UserRepositoryInterface
from app.modules.auth.services.auth_service import AuthService
from app.modules.auth.services.otp_service import OTPService
from app.modules.auth.services.token_service import TokenService
from app.modules.auth.services.user_service import UserService


def get_otp_repository(session: AsyncSession = Depends(get_db)) -> OTPRepositoryInterface:
    return OTPRepository(session)


def get_user_repository(session: AsyncSession = Depends(get_db)) -> UserRepositoryInterface:
    return UserRepository(session)


def get_athlete_profile_repository(
    session: AsyncSession = Depends(get_db),
) -> AthleteProfileRepositoryInterface:
    return AthleteProfileRepository(session)


def get_sms_provider() -> SMSProviderInterface:
    return TwilioSMSProvider()


def get_otp_service(
    repository: OTPRepositoryInterface = Depends(get_otp_repository),
    sms_provider: SMSProviderInterface = Depends(get_sms_provider),
) -> OTPService:
    return OTPService(repository, sms_provider)


def get_user_service(
    user_repository: UserRepositoryInterface = Depends(get_user_repository),
    athlete_repository: AthleteProfileRepositoryInterface = Depends(get_athlete_profile_repository),
) -> UserService:
    return UserService(user_repository, athlete_repository)


def get_token_service() -> TokenService:
    return TokenService()


def get_auth_service(
    otp_service: OTPService = Depends(get_otp_service),
    user_service: UserService = Depends(get_user_service),
    token_service: TokenService = Depends(get_token_service),
) -> AuthService:
    return AuthService(otp_service, user_service, token_service)
