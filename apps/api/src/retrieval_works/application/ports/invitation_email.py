from typing import Protocol


class InvitationEmailSender(Protocol):
    async def send_invitation(
        self, *, recipient: str, workspace_name: str, role: str, invitation_url: str
    ) -> None: ...
