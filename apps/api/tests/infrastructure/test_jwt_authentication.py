from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK, PyJWKClient
from jwt.algorithms import RSAAlgorithm

from devatlas.application.ports.authentication import InvalidCredentialError
from devatlas.infrastructure.authentication import (
    OidcJwksTokenVerifier,
    PyJwtTokenVerifier,
)

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


def test_oidc_verifier_resolves_rs256_key_and_validates_claims() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = RSAAlgorithm.to_jwk(private_key.public_key())
    signing_key = PyJWK.from_json(public_jwk)
    jwks_client = MagicMock(spec=PyJWKClient)
    jwks_client.get_signing_key_from_jwt.return_value = signing_key
    token = jwt.encode(
        {
            "iss": "https://identity.example.com/",
            "sub": "provider-user-123",
            "aud": "devatlas-api",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "current-key"},
    )
    verifier = OidcJwksTokenVerifier(
        jwks_url="https://identity.example.com/.well-known/jwks.json",
        issuer="https://identity.example.com/",
        audience="devatlas-api",
        jwks_client=jwks_client,
    )

    principal = verifier.verify(token)

    assert principal.issuer == "https://identity.example.com/"
    assert principal.subject == "provider-user-123"
    jwks_client.get_signing_key_from_jwt.assert_called_once_with(token)


def test_oidc_verifier_rejects_algorithm_confusion() -> None:
    jwks_client = MagicMock(spec=PyJWKClient)
    symmetric_key = PyJWK.from_dict({"kty": "oct", "k": "dGVzdC1zZWNyZXQ"})
    jwks_client.get_signing_key_from_jwt.return_value = symmetric_key
    token = _token()
    verifier = OidcJwksTokenVerifier(
        jwks_url="https://identity.example.com/.well-known/jwks.json",
        issuer="test-issuer",
        audience="devatlas-api",
        jwks_client=jwks_client,
    )

    with pytest.raises(InvalidCredentialError, match="invalid or expired"):
        verifier.verify(token)
