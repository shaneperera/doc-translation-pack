from __future__ import annotations

from doc_translation.pipeline.workspace import run_workspace


def test_workspace_is_isolated_and_cleaned_up() -> None:
    with run_workspace() as first:
        first_file = first / "result.docx"
        first_file.write_text("partial")

        with run_workspace() as second:
            assert first != second
            assert not (second / "result.docx").exists()

        assert first_file.exists()

    assert not first.exists()
