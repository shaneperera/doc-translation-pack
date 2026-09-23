"""Temporary workspace for one translation run."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory


@contextmanager
def run_workspace() -> Iterator[Path]:
    """Yield an isolated temporary directory and remove it when the run ends."""

    with TemporaryDirectory(prefix="doc-translation-") as directory:
        yield Path(directory)
