"""
Unit tests for `app.modules.auth.security.jwt`.

Covers the specific distinction this module makes between a token that is
genuinely invalid (bad signature, malformed, wrong type) and one that is
merely expired — a well-formed, correctly-signed token past its `exp`
must raise `TokenExpiredException`, not the generic `InvalidTokenException`,
so a client can tell "just log in again" apart from a real problem.
"""

from datetime import timedelta
from uuid import uuid4

import jwt as pyjwt
import pytest

from app.config.settings import get_settings
from app.modules.auth.constants import JWT_ALGORITHM
from app.modules.auth.exceptions import InvalidTokenException, TokenExpiredException
from app.modules.auth.security.jwt import create_access_token, create_refresh_token, decode_token
from app.utils.datetime import utc_now


def test_decode_token_round_trips_a_freshly_created_access_token():
    subject = uuid4()
    token = create_access_token(subject)

    claims = decode_token(token)

    assert claims["sub"] == str(subject)
    assert claims["type"] == "access"


def test_decode_token_round_trips_a_freshly_created_refresh_token():
    subject = uuid4()
    token = create_refresh_token(subject)

    claims = decode_token(token)

    assert claims["sub"] == str(subject)
    assert claims["type"] == "refresh"


def test_an_expired_but_correctly_signed_token_raises_token_expired_not_invalid_token():
    subject = uuid4()
    # 61 minutes in the past — past the 60-minute access-token TTL, signed
    # with the real, current SECRET_KEY (not tampered with).
    token = create_access_token(subject, expires_minutes=-61)

    with pytest.raises(TokenExpiredException):
        decode_token(token)


def test_a_token_signed_with_the_wrong_secret_raises_invalid_token_not_token_expired():
    settings = get_settings()
    payload = {
        "sub": str(uuid4()),
        "type": "access",
        "iat": utc_now(),
        "exp": utc_now() + timedelta(minutes=60),
    }
    wrong_secret = settings.SECRET_KEY + "-definitely-not-the-real-secret"
    tampered_token = pyjwt.encode(payload, wrong_secret, algorithm=JWT_ALGORITHM)

    with pytest.raises(InvalidTokenException):
        decode_token(tampered_token)


def test_a_malformed_token_raises_invalid_token():
    with pytest.raises(InvalidTokenException):
        decode_token("not-a-real-jwt")


def test_token_expired_and_invalid_token_have_distinct_error_codes():
    assert TokenExpiredException.error_code == "TOKEN_EXPIRED"
    assert InvalidTokenException.error_code == "INVALID_TOKEN"
    assert TokenExpiredException.error_code != InvalidTokenException.error_code
