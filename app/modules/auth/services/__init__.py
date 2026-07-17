"""Auth service interfaces — re-exported here for a single, stable import path."""

from app.modules.auth.services.auth_service import AuthService
from app.modules.auth.services.otp_service import OTPService
from app.modules.auth.services.token_service import TokenService
from app.modules.auth.services.user_service import UserService

__all__ = ["AuthService", "OTPService", "TokenService", "UserService"]
