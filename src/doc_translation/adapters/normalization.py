"""Normalize PDF inputs into ordered page rasters."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pymupdf

RASTER_DPI = 200


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

    @property
    def orientation(self) -> Literal["portrait", "landscape", "square"]:
        if self.width_points == self.height_points:
            return "square"
        return "landscape" if self.width_points > self.height_points else "portrait"


@dataclass(frozen=True)
class NormalizedInput:
    source_sha256: str
    pages: tuple[NormalizedPage, ...]


def normalize_input(source: Path, work_dir: Path) -> NormalizedInput:
    """Rasterize a PDF at 200 DPI into a caller-owned working directory."""

    if source.suffix.lower() != ".pdf":
        raise ValueError(f"unsupported input format: {source.suffix or '<none>'}")

    with source.open("rb") as source_file:
        source_sha256 = hashlib.file_digest(source_file, "sha256").hexdigest()

    work_dir.mkdir(parents=True, exist_ok=True)
    pages: list[NormalizedPage] = []
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
                )
            )

    return NormalizedInput(source_sha256=source_sha256, pages=tuple(pages))
