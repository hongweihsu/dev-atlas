from datetime import UTC, datetime, timedelta

import jwt
import pytest

from devatlas.application.ports.authentication import InvalidCredentialError
from devatlas.infrastructure.authentication import PyJwtTokenVerifier

SECRET = "test-secret-that-is-long-enough-for-local-tests"


def _token(**overrides: object) -> str:
    claims: dict[str, object] = {
        "iss": "test-issuer",
        "sub": "user-123",
        "aud": "devatlas-api",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_verifier_accepts_expected_issuer_subject_audience_and_expiry() -> None:
    verifier = PyJwtTokenVerifier(
        secret=SECRET, issuer="test-issuer", audience="devatlas-api"
    )

    principal = verifier.verify(_token())

    assert principal.issuer == "test-issuer"
    assert principal.subject == "user-123"


@pytest.mark.parametrize(
    "token",
    [
        _token(exp=datetime.now(UTC) - timedelta(seconds=1)),
        _token(iss="wrong-issuer"),
        _token(aud="wrong-audience"),
        jwt.encode(
            {
                "iss": "test-issuer",
                "sub": "user-123",
                "aud": "devatlas-api",
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            },
            "wrong-secret-that-is-also-at-least-32-bytes",
            algorithm="HS256",
        ),
    ],
)
def test_verifier_rejects_untrusted_or_expired_tokens(token: str) -> None:
    verifier = PyJwtTokenVerifier(
        secret=SECRET, issuer="test-issuer", audience="devatlas-api"
    )

    with pytest.raises(InvalidCredentialError, match="invalid or expired"):
        verifier.verify(token)
