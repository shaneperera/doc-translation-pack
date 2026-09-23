from __future__ import annotations

import pytest

from doc_translation.cli import main


def test_no_arguments_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: translate-doc" in capsys.readouterr().out
