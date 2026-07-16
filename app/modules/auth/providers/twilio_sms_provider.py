"""
Twilio-backed SMS provider.

Calls Twilio's REST API directly over `httpx` (async) rather than the
official synchronous `twilio` SDK, so a slow provider response can't block
the event loop. Credentials are read from `app.config.settings` (i.e. from
environment variables) — never hardcoded, and the auth token is never
logged.
"""

import re

import httpx
from loguru import logger

from app.config.settings import get_settings
from app.modules.auth.constants import PHONE_NUMBER_PATTERN
from app.modules.auth.exceptions import SMSDeliveryException
from app.modules.auth.providers.sms_provider import SMSProviderInterface

_TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"
_REQUEST_TIMEOUT_SECONDS = 10.0
# Twilio Messaging Service SIDs are always prefixed "MG"; anything else in
# `TWILIO_FROM_NUMBER` is expected to be a phone number.
_MESSAGING_SERVICE_SID_PREFIX = "MG"


def _describe_from(value: str) -> str:
    return "Messaging Service SID" if value.startswith(_MESSAGING_SERVICE_SID_PREFIX) else "phone number"


class TwilioSMSProvider(SMSProviderInterface):
    """Sends SMS messages via the Twilio Programmable Messaging REST API."""

    async def send(self, phone_number: str, message: str) -> None:
        settings = get_settings()
        from_value = settings.TWILIO_FROM_NUMBER
        url = f"{_TWILIO_API_BASE}/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
        payload = {
            "To": phone_number,
            "From": from_value,
            "Body": message,
        }
        auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN.get_secret_value())

        from_kind = _describe_from(from_value)
        if from_kind == "phone number" and not re.fullmatch(PHONE_NUMBER_PATTERN, from_value):
            logger.warning(
                "TWILIO_FROM_NUMBER {!r} does not look like a valid E.164 phone number or a "
                "Messaging Service SID (expected to start with 'MG') — Twilio will likely reject it.",
                from_value,
            )

        # Exact values sent to Twilio, logged for diagnosability. Never logged:
        # the auth token, or `message` (it contains the OTP in plaintext).
        logger.info(
            "Twilio request: To={} From={} (From is a {})",
            phone_number,
            from_value,
            from_kind,
        )

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(url, data=payload, auth=auth)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            # Twilio's own error response body is safe to log — it's their
            # diagnostic text (e.g. "unverified number", "invalid From"), not
            # a secret — and is the only way to distinguish *why* delivery
            # failed.
            twilio_detail = exc.response.text if isinstance(exc, httpx.HTTPStatusError) else ""
            logger.error(
                "SMS delivery failed: To={} From={} {} {}",
                phone_number,
                from_value,
                type(exc).__name__,
                twilio_detail,
            )
            raise SMSDeliveryException() from exc
