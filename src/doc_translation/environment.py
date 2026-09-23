"""Runtime dependency diagnostics that do not initialize external clients."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

MACOS_LIBREOFFICE = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")


@dataclass(frozen=True)
class EnvironmentCheck:
    """The observable result of one runtime prerequisite check."""

    name: str
    available: bool
    detail: str


def inspect_environment() -> tuple[EnvironmentCheck, ...]:
    """Inspect prerequisites without importing OpenAI, Streamlit, or LibreOffice."""

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    libreoffice_path = shutil.which("libreoffice") or shutil.which("soffice")
    if libreoffice_path is None and MACOS_LIBREOFFICE.is_file():
        libreoffice_path = str(MACOS_LIBREOFFICE)
    has_api_key = bool(os.environ.get("OPENAI_API_KEY", "").strip())

    return (
        EnvironmentCheck(
            name="python",
            available=sys.version_info[:2] == (3, 11),
            detail=f"Python {python_version}; required 3.11.x",
        ),
        EnvironmentCheck(
            name="libreoffice",
            available=libreoffice_path is not None,
            detail=libreoffice_path or "not found on PATH",
        ),
        EnvironmentCheck(
            name="openai_api_key",
            available=has_api_key,
            detail="configured" if has_api_key else "OPENAI_API_KEY is not set",
        ),
    )
