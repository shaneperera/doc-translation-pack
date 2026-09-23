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
        assert not page.dpi_assumed
        with Image.open(page.path) as raster:
            assert raster.size == (page.width_pixels, page.height_pixels)


def test_normalizes_png_using_embedded_dpi(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (400, 200)).save(source, dpi=(100, 100))

    page = normalize_input(source, tmp_path / "run").pages[0]

    assert (page.width_pixels, page.height_pixels) == (400, 200)
    assert page.dpi_x == pytest.approx(100, rel=0.001)
    assert page.dpi_y == pytest.approx(100, rel=0.001)
    assert not page.dpi_assumed
    assert page.width_points == pytest.approx(288, rel=0.001)
    assert page.height_points == pytest.approx(144, rel=0.001)
    assert page.orientation == "landscape"


@pytest.mark.parametrize("suffix", [".jpg", ".jpeg"])
def test_applies_exif_orientation_and_rotates_dpi(tmp_path: Path, suffix: str) -> None:
    source = tmp_path / f"source{suffix}"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (40, 20)).save(source, dpi=(100, 200), exif=exif)

    page = normalize_input(source, tmp_path / "run").pages[0]

    assert (page.width_pixels, page.height_pixels) == (20, 40)
    assert (page.dpi_x, page.dpi_y) == (200, 100)
    assert not page.dpi_assumed
    assert page.width_points == pytest.approx(7.2)
    assert page.height_points == pytest.approx(28.8)
    assert page.orientation == "portrait"
    with Image.open(page.path) as raster:
        assert raster.size == (20, 40)
        assert raster.getexif().get(274) is None


def test_assumes_200_dpi_when_image_has_no_physical_resolution(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (20, 10)).save(source)

    page = normalize_input(source, tmp_path / "run").pages[0]

    assert page.dpi_x == page.dpi_y == RASTER_DPI
    assert page.dpi_assumed
    assert page.width_points == pytest.approx(7.2)
    assert page.height_points == pytest.approx(3.6)


def test_rejects_unsupported_input_without_creating_work_dir(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("not a document")
    work_dir = tmp_path / "run"

    with pytest.raises(ValueError, match="unsupported input format: .txt"):
        normalize_input(source, work_dir)

    assert not work_dir.exists()
