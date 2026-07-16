"""
Auth repositories.

`AuthRepositoryInterface` remains an unimplemented placeholder for
athlete-account concerns (existing/new-user detection, athlete creation)
— out of scope until that phase. `OTPRepositoryInterface` /
`OTPRepository` are the concrete, working implementation for the Send OTP
feature's storage needs.
"""

from app.modules.auth.repositories.interfaces import AuthRepositoryInterface
from app.modules.auth.repositories.otp_repository import OTPRepository
from app.modules.auth.repositories.otp_repository_interface import OTPRepositoryInterface

__all__ = ["AuthRepositoryInterface", "OTPRepositoryInterface", "OTPRepository"]
