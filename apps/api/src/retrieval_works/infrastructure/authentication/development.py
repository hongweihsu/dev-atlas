from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt


@dataclass(frozen=True, slots=True)
class DevelopmentSession:
    access_token: str
    workspace_id: UUID
    expires_at: datetime


class DevelopmentSessionIssuer:
    """Issue local-only owner sessions when explicitly enabled by configuration."""

    def __init__(
        self,
        *,
        secret: str,
        issuer: str,
        audience: str,
        subject: str,
        workspace_id: UUID,
    ) -> None:
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._subject = subject
        self._workspace_id = workspace_id

    def issue(self) -> DevelopmentSession:
        expires_at = datetime.now(UTC) + timedelta(hours=8)
        access_token = jwt.encode(
            {
                "iss": self._issuer,
                "sub": self._subject,
                "aud": self._audience,
                "exp": expires_at,
            },
            self._secret,
            algorithm="HS256",
        )
        return DevelopmentSession(
            access_token=access_token,
            workspace_id=self._workspace_id,
            expires_at=expires_at,
        )
