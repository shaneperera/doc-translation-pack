from __future__ import annotations

import pytest

import doc_translation.cli as cli
from doc_translation.cli import main


def test_no_arguments_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: translate-doc" in capsys.readouterr().out


def test_translation_delegates_to_service(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: dict[str, object] = {}

    def fake_translate_input(*args: object, **kwargs: object) -> None:
        calls["args"] = args
        calls["kwargs"] = kwargs

    monkeypatch.setattr(cli, "translate_input", fake_translate_input)

    assert main(
        ["input.pdf", "-t", "de", "-o", "out.docx", "--source-language", "en", "--force"]
    ) == 0
    assert calls["kwargs"] == {
        "target_language": "de",
        "source_language": "en",
        "force": True,
    }
    assert "published: out.docx" in capsys.readouterr().out


def test_translation_failure_returns_two(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(*_: object, **__: object) -> None:
        raise ValueError("bad document")

    monkeypatch.setattr(cli, "translate_input", fail)

    assert main(["input.pdf", "-o", "out.docx"]) == 2
    assert "translation failed: bad document" in capsys.readouterr().err
