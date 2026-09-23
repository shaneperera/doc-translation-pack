"""Command-line entry point for document translation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from doc_translation import __version__
from doc_translation.environment import inspect_environment


def build_parser() -> argparse.ArgumentParser:
    """Build the public command parser without initializing optional dependencies."""

    parser = argparse.ArgumentParser(
        prog="translate-doc",
        description="Translate an image-only clinical document into validated editable DOCX.",
    )
    parser.add_argument(
        "--check-system",
        action="store_true",
        help="report runtime prerequisites without translating",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its process exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.check_system:
        checks = inspect_environment()
        for check in checks:
            label = "ok" if check.available else "missing"
            print(f"{check.name}: {label} ({check.detail})")
        return 0 if all(check.available for check in checks) else 1

    parser.print_help()
    return 0
