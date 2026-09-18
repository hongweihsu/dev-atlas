from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    issuer: str
    subject: str
    email: str | None = None


class InvalidCredentialError(ValueError):
    """Raised when a bearer credential cannot establish an identity."""


class TokenVerifier(Protocol):
    def verify(self, token: str) -> AuthenticatedPrincipal: ...
