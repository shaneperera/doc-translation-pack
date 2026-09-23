"""Dependency-independent DOCX editability inspection."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import pymupdf

from doc_translation.domain.document import PageIR

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DRAWING = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
DRAWING_MAIN = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
MACOS_LIBREOFFICE = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")


@dataclass(frozen=True)
class DocxInspection:
    editable_text_count: int
    bookmark_count: int
    page_sized_raster_count: int


def inspect_docx(path: Path) -> DocxInspection:
    """Count editable text nodes and page-sized raster drawings in a DOCX."""

    with ZipFile(path) as package:
        root = ElementTree.fromstring(package.read("word/document.xml"))
        text_count = len(root.findall(f".//{WORD}t"))
        bookmark_count = len(root.findall(f".//{WORD}bookmarkStart"))
        page_sizes = root.findall(f".//{WORD}pgSz")
        raster_count = 0
        drawings = root.findall(f".//{DRAWING}inline") + root.findall(
            f".//{DRAWING}anchor"
        )
        for drawing in drawings:
            extent = drawing.find(f"{DRAWING}extent")
            if extent is None or drawing.find(f".//{DRAWING_MAIN}blip") is None:
                continue
            width = int(extent.get("cx", "0"))
            height = int(extent.get("cy", "0"))
            for page_size in page_sizes:
                page_width = int(page_size.get(f"{WORD}w", "0")) * 635
                page_height = int(page_size.get(f"{WORD}h", "0")) * 635
                if abs(width - page_width) < 100_000 and abs(height - page_height) < 100_000:
                    raster_count += 1
                    break
    return DocxInspection(text_count, bookmark_count, raster_count)


def find_libreoffice() -> str | None:
    """Return the available LibreOffice executable, if installed."""

    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if executable is not None:
        return executable
    return str(MACOS_LIBREOFFICE) if MACOS_LIBREOFFICE.is_file() else None


def render_docx_pdf(path: Path, output_dir: Path) -> Path:
    """Render a DOCX to PDF through LibreOffice."""

    executable = find_libreoffice()
    if executable is None:
        raise RuntimeError("LibreOffice is required for DOCX publication validation")
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = (output_dir / "libreoffice-profile").resolve().as_uri()
    subprocess.run(
        [
            executable,
            f"-env:UserInstallation={profile}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    pdf_path = output_dir / f"{path.stem}.pdf"
    if not pdf_path.is_file():
        raise RuntimeError("LibreOffice did not produce a PDF")
    return pdf_path


def validate_docx_for_publication(
    path: Path, source_pages: Sequence[PageIR], output_dir: Path
) -> Path:
    """Reject a DOCX unless editability and rendered source-page parity hold."""

    inspection = inspect_docx(path)
    if inspection.editable_text_count == 0:
        raise ValueError("publication validation found no editable text")
    if inspection.bookmark_count == 0:
        raise ValueError("publication validation found no region bookmarks")
    if inspection.page_sized_raster_count:
        raise ValueError("publication validation found a full-page raster")

    pdf_path = render_docx_pdf(path, output_dir)
    with pymupdf.open(pdf_path) as rendered:  # type: ignore[no-untyped-call]
        if len(rendered) != len(source_pages):
            raise ValueError(
                "publication validation page count mismatch: "
                f"expected {len(source_pages)}, got {len(rendered)}"
            )
        for source_page, rendered_page in zip(source_pages, rendered, strict=True):
            width_error = abs(rendered_page.rect.width - source_page.geometry.width_points)
            height_error = abs(rendered_page.rect.height - source_page.geometry.height_points)
            if width_error > 1 or height_error > 1:
                raise ValueError(
                    "publication validation page size mismatch: "
                    f"page {source_page.page_number}"
                )
    return pdf_path


def roundtrip_docx(path: Path, output_dir: Path) -> tuple[Path, Path]:
    """Render a DOCX to PDF and reopen it through LibreOffice as DOCX."""

    executable = find_libreoffice()
    if executable is None:
        raise RuntimeError("LibreOffice is required for DOCX round-trip validation")
    output_dir.mkdir(parents=True, exist_ok=True)
    for target in ("pdf", "docx"):
        subprocess.run(
            [
                executable,
                "--headless",
                "--convert-to",
                target,
                "--outdir",
                str(output_dir),
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    return output_dir / f"{path.stem}.pdf", output_dir / path.name
