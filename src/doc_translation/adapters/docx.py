"""Minimal native DOCX rendering for text regions."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.shared import Inches

from doc_translation.domain.document import DocumentIR, PageIR


def _configure_page(section: object, page: PageIR) -> None:
    width_inches = page.geometry.width_points / 72
    height_inches = page.geometry.height_points / 72
    section.page_width = Inches(width_inches)  # type: ignore[attr-defined]
    section.page_height = Inches(height_inches)  # type: ignore[attr-defined]
    if width_inches > height_inches:
        section.orientation = WD_ORIENT.LANDSCAPE  # type: ignore[attr-defined]
    else:
        section.orientation = WD_ORIENT.PORTRAIT  # type: ignore[attr-defined]


def render_text_docx(
    document_ir: DocumentIR,
    translated_text: Mapping[str, str],
    output_path: Path,
) -> None:
    """Render text regions as editable Word paragraphs with source page sizes."""

    document = Document()
    for page_index, page in enumerate(document_ir.pages):
        if page_index == 0:
            section = document.sections[0]
        else:
            section = document.add_section(WD_SECTION.NEW_PAGE)
        _configure_page(section, page)

        regions_by_id = {region.region_id: region for region in page.regions}
        for region_id in page.reading_order:
            region = regions_by_id[region_id]
            if region.kind != "text":
                raise ValueError(f"unsupported region kind for Cycle 6.1: {region.kind}")
            if region.translation_eligible and region_id not in translated_text:
                raise ValueError(f"missing translated text: {region_id}")
            text = translated_text.get(region_id, region.source_text or "")
            document.add_paragraph(text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
