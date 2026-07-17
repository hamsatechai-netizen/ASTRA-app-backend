"""
Unit tests for `OTPService.verify_otp`.

Uses a fake `OTPRepositoryInterface` (in-memory) rather than a real
database connection — these test the service's decision logic (expiry,
attempt limits, hash comparison, consumption), not persistence.
"""

from datetime import datetime, timedelta

import pytest
from app.models.otp_challenge import OTPChallenge
from app.modules.auth.constants import OTP_MAX_VERIFICATION_ATTEMPTS
from app.modules.auth.exceptions import InvalidOTPException, OTPExpiredException, TooManyAttemptsException
from app.modules.auth.repositories.otp_repository_interface import OTPRepositoryInterface
from app.modules.auth.security import hash_otp
from app.modules.auth.services.otp_service import OTPService
from app.utils.datetime import utc_now

PHONE = "+919876543210"
CODE = "123456"


class FakeOTPRepository(OTPRepositoryInterface):
    def __init__(self) -> None:
        self.records: dict[str, OTPChallenge] = {}

    async def get_by_phone(self, phone_number: str) -> OTPChallenge | None:
        return self.records.get(phone_number)

    async def upsert(self, phone_number: str, otp_hash: str, expires_at: datetime) -> OTPChallenge:
        challenge = OTPChallenge(
            phone_number=phone_number, otp_hash=otp_hash, expires_at=expires_at, attempts=0
        )
        self.records[phone_number] = challenge
        return challenge

    async def increment_attempts(self, phone_number: str) -> int:
        challenge = self.records[phone_number]
        challenge.attempts += 1
        return challenge.attempts

    async def delete_by_phone(self, phone_number: str) -> None:
        self.records.pop(phone_number, None)


def _seed(repo: FakeOTPRepository, *, attempts: int = 0, expires_in_seconds: int = 300) -> None:
    repo.records[PHONE] = OTPChallenge(
        phone_number=PHONE,
        otp_hash=hash_otp(CODE),
        expires_at=utc_now() + timedelta(seconds=expires_in_seconds),
        attempts=attempts,
    )


async def test_verify_otp_success_consumes_the_challenge() -> None:
    repo = FakeOTPRepository()
    _seed(repo)
    service = OTPService(repo, sms_provider=None)  # type: ignore[arg-type]

    await service.verify_otp(PHONE, CODE)

    assert repo.records.get(PHONE) is None


async def test_verify_otp_no_challenge_raises_invalid() -> None:
    repo = FakeOTPRepository()
    service = OTPService(repo, sms_provider=None)  # type: ignore[arg-type]

    with pytest.raises(InvalidOTPException):
        await service.verify_otp(PHONE, CODE)


async def test_verify_otp_wrong_code_increments_attempts_and_raises_invalid() -> None:
    repo = FakeOTPRepository()
    _seed(repo)
    service = OTPService(repo, sms_provider=None)  # type: ignore[arg-type]

    with pytest.raises(InvalidOTPException):
        await service.verify_otp(PHONE, "000000")

    assert repo.records[PHONE].attempts == 1


async def test_verify_otp_expired_raises_expired() -> None:
    repo = FakeOTPRepository()
    _seed(repo, expires_in_seconds=-10)
    service = OTPService(repo, sms_provider=None)  # type: ignore[arg-type]

    with pytest.raises(OTPExpiredException):
        await service.verify_otp(PHONE, CODE)


async def test_verify_otp_too_many_attempts_raises_before_checking_code() -> None:
    repo = FakeOTPRepository()
    _seed(repo, attempts=OTP_MAX_VERIFICATION_ATTEMPTS)
    service = OTPService(repo, sms_provider=None)  # type: ignore[arg-type]

    with pytest.raises(TooManyAttemptsException):
        await service.verify_otp(PHONE, CODE)
