"""Command line of the app: python -m app.cli <command> (tech.md §4.1)."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from app.config import Settings
from app.main import create_app


def openapi(out: Path) -> None:
    # A local .env must not leak into the committed schema.
    schema = create_app(Settings(_env_file=None)).openapi()
    text = json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("openapi", help="write the OpenAPI schema (just gen)")
    gen.add_argument("out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "openapi":
        openapi(args.out)


if __name__ == "__main__":
    main()
