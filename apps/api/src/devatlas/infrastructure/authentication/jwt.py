import jwt
from jwt.exceptions import InvalidTokenError

from devatlas.application.ports.authentication import (
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
        except InvalidTokenError as error:
            raise InvalidCredentialError(
                "bearer token is invalid or expired"
            ) from error

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise InvalidCredentialError("bearer token subject is invalid")
        return AuthenticatedPrincipal(issuer=self._issuer, subject=subject)
