from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK, PyJWKClient
from jwt.algorithms import RSAAlgorithm

from devatlas.application.ports.authentication import InvalidCredentialError
from devatlas.infrastructure.authentication import (
    CognitoAccessTokenVerifier,
    CognitoIdentityTokenVerifier,
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


def test_cognito_verifier_accepts_only_access_token_for_expected_client() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signing_key = PyJWK.from_json(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwks_client = MagicMock(spec=PyJWKClient)
    jwks_client.get_signing_key_from_jwt.return_value = signing_key
    token = jwt.encode(
        {
            "iss": "https://cognito-idp.ap-southeast-2.amazonaws.com/pool",
            "sub": "cognito-user-123",
            "client_id": "web-client-123",
            "token_use": "access",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
    )
    verifier = CognitoAccessTokenVerifier(
        jwks_url="https://cognito.example.com/.well-known/jwks.json",
        issuer="https://cognito-idp.ap-southeast-2.amazonaws.com/pool",
        client_id="web-client-123",
        jwks_client=jwks_client,
    )

    assert verifier.verify(token).subject == "cognito-user-123"


def test_cognito_identity_verifier_requires_and_normalizes_verified_email() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signing_key = PyJWK.from_json(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwks_client = MagicMock(spec=PyJWKClient)
    jwks_client.get_signing_key_from_jwt.return_value = signing_key
    token = jwt.encode(
        {
            "iss": "https://cognito-idp.ap-southeast-2.amazonaws.com/pool",
            "sub": "cognito-user-123",
            "aud": "web-client-123",
            "token_use": "id",
            "email": "Reader@Example.COM",
            "email_verified": True,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
    )
    verifier = CognitoIdentityTokenVerifier(
        jwks_url="https://cognito.example.com/.well-known/jwks.json",
        issuer="https://cognito-idp.ap-southeast-2.amazonaws.com/pool",
        client_id="web-client-123",
        jwks_client=jwks_client,
    )

    principal = verifier.verify(token)

    assert principal.subject == "cognito-user-123"
    assert principal.email == "reader@example.com"


@pytest.mark.parametrize(
    ("token_use", "client_id", "message"),
    [("id", "web-client-123", "not an access token"), ("access", "other", "client")],
)
def test_cognito_verifier_rejects_wrong_token_type_or_client(
    token_use: str, client_id: str, message: str
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signing_key = PyJWK.from_json(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwks_client = MagicMock(spec=PyJWKClient)
    jwks_client.get_signing_key_from_jwt.return_value = signing_key
    token = jwt.encode(
        {
            "iss": "https://cognito-idp.ap-southeast-2.amazonaws.com/pool",
            "sub": "cognito-user-123",
            "client_id": client_id,
            "token_use": token_use,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
    )
    verifier = CognitoAccessTokenVerifier(
        jwks_url="https://cognito.example.com/.well-known/jwks.json",
        issuer="https://cognito-idp.ap-southeast-2.amazonaws.com/pool",
        client_id="web-client-123",
        jwks_client=jwks_client,
    )

    with pytest.raises(InvalidCredentialError, match=message):
        verifier.verify(token)
