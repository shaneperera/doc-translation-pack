"""Command-line entry point for document translation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from doc_translation import __version__
from doc_translation.environment import inspect_environment
from doc_translation.pipeline.service import translate_input


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
    parser.add_argument("input", nargs="?", type=Path, help="source PDF or image")
    parser.add_argument("-t", "--target-language", default="en")
    parser.add_argument("-o", "--output", type=Path, help="published DOCX path")
    parser.add_argument("--source-language")
    parser.add_argument("--force", action="store_true")
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

    if args.input is None and args.output is None:
        parser.print_help()
        return 0
    if args.input is None or args.output is None:
        parser.error("INPUT and --output are required")

    try:
        translate_input(
            args.input,
            args.output,
            target_language=args.target_language,
            source_language=args.source_language,
            force=args.force,
        )
    except Exception as error:
        print(f"translation failed: {error}", file=sys.stderr)
        return 2

    print(f"published: {args.output}")
    print(f"audit: {args.output.with_suffix('.audit.json')}")
    return 0
