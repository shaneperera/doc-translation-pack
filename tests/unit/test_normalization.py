from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from doc_translation.adapters.normalization import RASTER_DPI, normalize_input


def test_normalizes_multipage_pdf_with_source_geometry(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    with pymupdf.open() as document:  # type: ignore[no-untyped-call]
        document.new_page(width=123, height=257)
        document.new_page(width=333, height=111)
        document.save(source)

    result = normalize_input(source, tmp_path / "run")

    assert result.source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert [page.page_number for page in result.pages] == [1, 2]
    assert [page.orientation for page in result.pages] == ["portrait", "landscape"]

    for page, expected_points in zip(result.pages, [(123, 257), (333, 111)], strict=True):
        expected_width = round(expected_points[0] * RASTER_DPI / 72)
        expected_height = round(expected_points[1] * RASTER_DPI / 72)

        assert page.width_points == pytest.approx(expected_points[0])
        assert page.height_points == pytest.approx(expected_points[1])
        assert abs(page.width_pixels - expected_width) <= 1
        assert abs(page.height_pixels - expected_height) <= 1
        assert page.dpi_x == page.dpi_y == RASTER_DPI
        with Image.open(page.path) as raster:
            assert raster.size == (page.width_pixels, page.height_pixels)


def test_rejects_unsupported_input_without_creating_work_dir(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("not a document")
    work_dir = tmp_path / "run"

    with pytest.raises(ValueError, match="unsupported input format: .txt"):
        normalize_input(source, work_dir)

    assert not work_dir.exists()
