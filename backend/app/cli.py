"""Command line of the app: python -m app.cli <command> (tech.md §4.1)."""

import argparse
import asyncio
import getpass
import json
import sys
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings
from app.core.errors import AppError
from app.core.security import RateLimiter
from app.db.base import UnitOfWork
from app.domains.auth.service import AuthService
from app.main import create_app


def openapi(out: Path) -> None:
    # A local .env must not leak into the committed schema.
    schema = create_app(Settings(_env_file=None)).openapi()
    text = json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")


def with_auth[T](action: Callable[[AuthService, Settings], Awaitable[T]]) -> T:
    """Runs an account command on the database of the environment and .env."""

    async def run() -> T:
        settings = Settings()
        engine = create_async_engine(settings.DATABASE_URL.get_secret_value())
        try:
            return await action(AuthService(UnitOfWork(engine), settings, RateLimiter()), settings)
        finally:
            await engine.dispose()

    # psycopg's async mode cannot run on the Windows Proactor loop.
    return asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


async def print_invites(auth: AuthService, settings: Settings, count: int) -> None:
    for code in await auth.create_invites(count):
        sys.stdout.write(f"{settings.APP_BASE_URL}/register?invite={code}\n")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("openapi", help="write the OpenAPI schema (just gen)")
    gen.add_argument("out", type=Path)
    invites = commands.add_parser("invites", help="registration invites (just invites <n>)")
    actions = invites.add_subparsers(dest="action", required=True)
    create = actions.add_parser("create", help="print links with new invite codes")
    create.add_argument("--count", type=int, default=1)
    owner = commands.add_parser(
        "create-owner", help="create the owner or make a user the owner; asks for the password"
    )
    owner.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "openapi":
            openapi(args.out)
        elif args.command == "invites":
            if args.count < 1:
                parser.error("--count must be positive")
            with_auth(lambda auth, settings: print_invites(auth, settings, args.count))
        else:
            password = getpass.getpass("Password: ")
            if getpass.getpass("Repeat the password: ") != password:
                parser.exit(1, "The passwords differ\n")
            with_auth(lambda auth, _: auth.create_owner(args.email, password))
    except AppError as error:
        parser.exit(1, f"{error.message}\n")


if __name__ == "__main__":
    main()
