"""Dependency-independent DOCX editability inspection."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DRAWING = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
DRAWING_MAIN = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


@dataclass(frozen=True)
class DocxInspection:
    editable_text_count: int
    page_sized_raster_count: int


def inspect_docx(path: Path) -> DocxInspection:
    """Count editable text nodes and page-sized raster drawings in a DOCX."""

    with ZipFile(path) as package:
        root = ElementTree.fromstring(package.read("word/document.xml"))
        text_count = len(root.findall(f".//{WORD}t"))
        page_sizes = root.findall(f".//{WORD}pgSz")
        raster_count = 0
        for inline in root.findall(f".//{DRAWING}inline"):
            extent = inline.find(f"{DRAWING}extent")
            if extent is None or inline.find(f".//{DRAWING_MAIN}blip") is None:
                continue
            width = int(extent.get("cx", "0"))
            height = int(extent.get("cy", "0"))
            for page_size in page_sizes:
                page_width = int(page_size.get(f"{WORD}w", "0")) * 12_700
                page_height = int(page_size.get(f"{WORD}h", "0")) * 12_700
                if abs(width - page_width) < 100_000 and abs(height - page_height) < 100_000:
                    raster_count += 1
                    break
    return DocxInspection(text_count, raster_count)


def find_libreoffice() -> str | None:
    """Return the available LibreOffice executable, if installed."""

    return shutil.which("libreoffice") or shutil.which("soffice")
