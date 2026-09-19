import asyncio
from typing import Any


class SesInvitationEmailSender:
    def __init__(self, *, region: str, sender: str) -> None:
        import boto3  # type: ignore[import-untyped]

        self._client: Any = boto3.client("sesv2", region_name=region)
        self._sender = sender

    async def send_invitation(
        self, *, recipient: str, workspace_name: str, role: str, invitation_url: str
    ) -> None:
        subject = f"You were invited to {workspace_name} on Retrieval Works"
        body = (
            f"You were invited as {role} to the Retrieval Works workspace "
            f"{workspace_name}.\n\nAccept the invitation (valid for 7 days):\n"
            f"{invitation_url}\n\n"
            "If you did not expect this invitation, ignore this email."
        )
        await asyncio.to_thread(
            self._client.send_email,
            FromEmailAddress=self._sender,
            Destination={"ToAddresses": [recipient]},
            Content={
                "Simple": {
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": body}},
                }
            },
        )
