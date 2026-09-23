"""Normalize PDF and image inputs into ordered page rasters."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pymupdf
from PIL import Image, ImageOps

RASTER_DPI = 200
SUPPORTED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}
EXIF_ORIENTATION = 274
QUARTER_TURN_ORIENTATIONS = {5, 6, 7, 8}


@dataclass(frozen=True)
class NormalizedPage:
    page_number: int
    path: Path
    width_pixels: int
    height_pixels: int
    width_points: float
    height_points: float
    dpi_x: float
    dpi_y: float
    dpi_assumed: bool

    @property
    def orientation(self) -> Literal["portrait", "landscape", "square"]:
        if self.width_points == self.height_points:
            return "square"
        if self.width_points > self.height_points:
            return "landscape"
        return "portrait"


@dataclass(frozen=True)
class NormalizedInput:
    source_sha256: str
    pages: tuple[NormalizedPage, ...]


def _image_dpi(image: Image.Image) -> tuple[float, float, bool]:
    # If density unit in JFIF metadata is 0, assume the dpi is 200
    if image.format == "JPEG" and image.info.get("jfif_unit") == 0:
        return RASTER_DPI, RASTER_DPI, True

    value = image.info.get("dpi")
    if not isinstance(value, tuple) or len(value) != 2:
        return RASTER_DPI, RASTER_DPI, True

    dpi_x, dpi_y = value
    if not isinstance(dpi_x, (int, float)) or not isinstance(dpi_y, (int, float)):
        return RASTER_DPI, RASTER_DPI, True
    if dpi_x <= 0 or dpi_y <= 0:
        return RASTER_DPI, RASTER_DPI, True

    return float(dpi_x), float(dpi_y), False


def normalize_input(source: Path, work_dir: Path) -> NormalizedInput:
    """Normalize a PDF or image into ordered PNG pages in a working directory."""

    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported input format: {source.suffix or '<none>'}")

    with source.open("rb") as source_file:
        source_sha256 = hashlib.file_digest(source_file, "sha256").hexdigest()

    work_dir.mkdir(parents=True, exist_ok=True)
    pages: list[NormalizedPage] = []
    if suffix == ".pdf":
        with pymupdf.open(source) as document:  # type: ignore[no-untyped-call]
            for page_number, page in enumerate(document, start=1):
                raster = page.get_pixmap(dpi=RASTER_DPI, alpha=False)
                raster_path = work_dir / f"page-{page_number:04d}.png"
                raster.save(raster_path)
                pages.append(
                    NormalizedPage(
                        page_number=page_number,
                        path=raster_path,
                        width_pixels=raster.width,
                        height_pixels=raster.height,
                        width_points=page.rect.width,
                        height_points=page.rect.height,
                        dpi_x=RASTER_DPI,
                        dpi_y=RASTER_DPI,
                        dpi_assumed=False,
                    )
                )
    else:
        with Image.open(source) as image:
            dpi_x, dpi_y, dpi_assumed = _image_dpi(image)
            if image.getexif().get(EXIF_ORIENTATION, 1) in QUARTER_TURN_ORIENTATIONS:
                dpi_x, dpi_y = dpi_y, dpi_x
            raster = ImageOps.exif_transpose(image)
            if raster.mode == "CMYK":
                raster = raster.convert("RGB")
            raster_path = work_dir / "page-0001.png"
            raster.save(raster_path, dpi=(dpi_x, dpi_y))
            pages.append(
                NormalizedPage(
                    page_number=1,
                    path=raster_path,
                    width_pixels=raster.width,
                    height_pixels=raster.height,
                    width_points=raster.width * 72 / dpi_x,
                    height_points=raster.height * 72 / dpi_y,
                    dpi_x=dpi_x,
                    dpi_y=dpi_y,
                    dpi_assumed=dpi_assumed,
                )
            )

    return NormalizedInput(source_sha256=source_sha256, pages=tuple(pages))
