"""
Service/repository/provider construction for FastAPI's DI system.

Each function is a `Depends()`-compatible provider; chaining them (as
`get_otp_service` and `get_auth_service` do) is how the router ends up
with a fully-wired `AuthService` per request without constructing
anything itself.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.modules.auth.providers.sms_provider import SMSProviderInterface
from app.modules.auth.providers.twilio_sms_provider import TwilioSMSProvider
from app.modules.auth.repositories.otp_repository import OTPRepository
from app.modules.auth.repositories.otp_repository_interface import OTPRepositoryInterface
from app.modules.auth.services.auth_service import AuthService
from app.modules.auth.services.otp_service import OTPService
from app.modules.auth.services.token_service import TokenService


def get_otp_repository(session: AsyncSession = Depends(get_db)) -> OTPRepositoryInterface:
    return OTPRepository(session)


def get_sms_provider() -> SMSProviderInterface:
    return TwilioSMSProvider()


def get_otp_service(
    repository: OTPRepositoryInterface = Depends(get_otp_repository),
    sms_provider: SMSProviderInterface = Depends(get_sms_provider),
) -> OTPService:
    return OTPService(repository, sms_provider)


def get_auth_service(otp_service: OTPService = Depends(get_otp_service)) -> AuthService:
    # TokenService currently has no constructor dependencies of its own — its
    # methods are unimplemented stubs (token issuance is a later phase) — so
    # constructing a plain instance here is free and calls nothing.
    return AuthService(otp_service, TokenService())
