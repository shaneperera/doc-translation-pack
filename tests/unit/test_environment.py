from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from doc_translation.environment import inspect_environment


def test_environment_checks_report_missing_external_requirements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr(
        "doc_translation.environment.MACOS_LIBREOFFICE", Path("/missing/soffice")
    )

    checks = inspect_environment()
    checks_by_name = {check.name: check for check in checks}

    assert checks_by_name["python"].available
    assert not checks_by_name["libreoffice"].available
    assert not checks_by_name["openai_api_key"].available
