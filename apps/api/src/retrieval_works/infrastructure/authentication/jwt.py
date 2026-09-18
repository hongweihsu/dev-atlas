import jwt
from jwt import PyJWK, PyJWKClient
from jwt.exceptions import PyJWTError

from retrieval_works.application.ports.authentication import (
    AuthenticatedPrincipal,
    InvalidCredentialError,
)


class PyJwtTokenVerifier:
    """Verify locally signed access tokens with pinned security parameters."""

    def __init__(self, *, secret: str, issuer: str, audience: str) -> None:
        if not secret:
            raise ValueError("JWT secret must not be empty")
        self._secret = secret
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> AuthenticatedPrincipal:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["exp", "iss", "sub", "aud"]},
            )
        except PyJWTError as error:
            raise InvalidCredentialError(
                "bearer token is invalid or expired"
            ) from error

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise InvalidCredentialError("bearer token subject is invalid")
        return AuthenticatedPrincipal(issuer=self._issuer, subject=subject)


class OidcJwksTokenVerifier:
    """Verify provider-issued access tokens against a cached remote JWKS."""

    def __init__(
        self,
        *,
        jwks_url: str,
        issuer: str,
        audience: str,
        jwks_client: PyJWKClient | None = None,
    ) -> None:
        if not jwks_url.startswith("https://"):
            raise ValueError("OIDC JWKS URL must use HTTPS")
        self._jwks_client = jwks_client or PyJWKClient(jwks_url)
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> AuthenticatedPrincipal:
        try:
            signing_key: PyJWK = self._jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["exp", "iss", "sub", "aud"]},
            )
        except PyJWTError as error:
            raise InvalidCredentialError(
                "bearer token is invalid or expired"
            ) from error

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise InvalidCredentialError("bearer token subject is invalid")
        return AuthenticatedPrincipal(issuer=self._issuer, subject=subject)


class CognitoAccessTokenVerifier:
    """Verify Cognito access tokens, whose client binding is `client_id`."""

    def __init__(
        self,
        *,
        jwks_url: str,
        issuer: str,
        client_id: str,
        jwks_client: PyJWKClient | None = None,
    ) -> None:
        if not jwks_url.startswith("https://"):
            raise ValueError("Cognito JWKS URL must use HTTPS")
        if not client_id:
            raise ValueError("Cognito client ID must not be empty")
        self._jwks_client = jwks_client or PyJWKClient(jwks_url)
        self._issuer = issuer
        self._client_id = client_id

    def verify(self, token: str) -> AuthenticatedPrincipal:
        try:
            signing_key: PyJWK = self._jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                options={
                    "verify_aud": False,
                    "require": ["client_id", "exp", "iss", "sub", "token_use"],
                },
            )
        except PyJWTError as error:
            raise InvalidCredentialError(
                "bearer token is invalid or expired"
            ) from error

        if claims.get("token_use") != "access":
            raise InvalidCredentialError("bearer token is not an access token")
        if claims.get("client_id") != self._client_id:
            raise InvalidCredentialError("bearer token client is invalid")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise InvalidCredentialError("bearer token subject is invalid")
        return AuthenticatedPrincipal(issuer=self._issuer, subject=subject)


class CognitoIdentityTokenVerifier:
    """Verify Cognito ID tokens and expose only a verified email identity."""

    def __init__(
        self,
        *,
        jwks_url: str,
        issuer: str,
        client_id: str,
        jwks_client: PyJWKClient | None = None,
    ) -> None:
        self._jwks_client = jwks_client or PyJWKClient(jwks_url)
        self._issuer = issuer
        self._client_id = client_id

    def verify(self, token: str) -> AuthenticatedPrincipal:
        try:
            signing_key: PyJWK = self._jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._client_id,
                options={"require": ["aud", "email", "exp", "iss", "sub", "token_use"]},
            )
        except PyJWTError as error:
            raise InvalidCredentialError(
                "identity token is invalid or expired"
            ) from error
        if claims.get("token_use") != "id":
            raise InvalidCredentialError("identity token is not an ID token")
        email = claims.get("email")
        if claims.get("email_verified") is not True or not isinstance(email, str):
            raise InvalidCredentialError("identity token email is not verified")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise InvalidCredentialError("identity token subject is invalid")
        return AuthenticatedPrincipal(
            issuer=self._issuer,
            subject=subject,
            email=email.strip().casefold(),
        )
