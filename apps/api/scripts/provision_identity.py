"""Idempotently grant a verified external identity access to a workspace."""

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select

from devatlas.core.config import get_settings
from devatlas.core.tenancy import LEGACY_WORKSPACE_ID
from devatlas.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from devatlas.infrastructure.models import User, Workspace, WorkspaceMembership


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name")
    parser.add_argument("--workspace-id", type=UUID, default=LEGACY_WORKSPACE_ID)
    parser.add_argument(
        "--role", choices=("owner", "editor", "viewer"), default="owner"
    )
    return parser.parse_args()


async def provision(arguments: argparse.Namespace) -> None:
    engine = create_database_engine(get_settings().database_url)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory.begin() as session:
            workspace = await session.get(Workspace, arguments.workspace_id)
            if workspace is None:
                raise SystemExit(f"workspace does not exist: {arguments.workspace_id}")

            user = await session.scalar(
                select(User).where(
                    User.identity_issuer == arguments.issuer,
                    User.identity_subject == arguments.subject,
                )
            )
            if user is None:
                user = User(
                    identity_issuer=arguments.issuer,
                    identity_subject=arguments.subject,
                    email=arguments.email,
                    display_name=arguments.display_name,
                )
                session.add(user)
                await session.flush()
            else:
                user.email = arguments.email
                user.display_name = arguments.display_name

            membership = await session.get(
                WorkspaceMembership,
                (arguments.workspace_id, user.id),
            )
            if membership is None:
                session.add(
                    WorkspaceMembership(
                        workspace_id=arguments.workspace_id,
                        user_id=user.id,
                        role=arguments.role,
                    )
                )
            else:
                membership.role = arguments.role

        print(
            f"provisioned {arguments.email} as {arguments.role} "
            f"in workspace {arguments.workspace_id}"
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(provision(parse_arguments()))
