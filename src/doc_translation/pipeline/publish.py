"""Atomic publication of validated pipeline artifacts."""

from __future__ import annotations

import os
from pathlib import Path


def publish_file(source: Path, destination: Path, *, force: bool = False) -> None:
    """Replace a destination with a completed source file in one filesystem operation."""

    if not source.is_file():
        raise FileNotFoundError(source)
    if destination.exists() and not force:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, destination)
