from __future__ import annotations

from pathlib import Path

import pytest

from doc_translation.pipeline.publish import publish_file


def test_publishes_completed_file_atomically(tmp_path: Path) -> None:
    source = tmp_path / "run" / "result.docx"
    destination = tmp_path / "outputs" / "result.docx"
    source.parent.mkdir()
    source.write_text("complete")

    publish_file(source, destination)

    assert destination.read_text() == "complete"
    assert not source.exists()


def test_refuses_existing_destination_without_force(tmp_path: Path) -> None:
    source = tmp_path / "result.docx"
    destination = tmp_path / "published.docx"
    source.write_text("new")
    destination.write_text("old")

    with pytest.raises(FileExistsError):
        publish_file(source, destination)

    assert destination.read_text() == "old"
    assert source.read_text() == "new"


def test_force_replaces_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "result.docx"
    destination = tmp_path / "published.docx"
    source.write_text("new")
    destination.write_text("old")

    publish_file(source, destination, force=True)

    assert destination.read_text() == "new"
