"""Minimal native DOCX rendering for text regions."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
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


def _add_bookmark(element: object, region_id: str, bookmark_id: int) -> None:
    bookmark_start = OxmlElement("w:bookmarkStart")
    bookmark_start.set(qn("w:id"), str(bookmark_id))
    bookmark_start.set(qn("w:name"), region_id.replace("-", "_"))
    bookmark_end = OxmlElement("w:bookmarkEnd")
    bookmark_end.set(qn("w:id"), str(bookmark_id))
    parent = element.getparent()  # type: ignore[attr-defined]
    index = parent.index(element)
    parent.insert(index, bookmark_start)
    parent.insert(index + 2, bookmark_end)


def _text_for_region(region: object, translated_text: Mapping[str, str]) -> str:
    region_id = region.region_id  # type: ignore[attr-defined]
    if region.translation_eligible and region_id not in translated_text:  # type: ignore[attr-defined]
        raise ValueError(f"missing translated text: {region_id}")
    return translated_text.get(region_id, region.source_text or "")  # type: ignore[attr-defined]


def render_text_docx(
    document_ir: DocumentIR,
    translated_text: Mapping[str, str],
    output_path: Path,
) -> None:
    """Render supported regions as editable Word content with source page sizes."""

    document = Document()
    bookmark_id = 1
    for page_index, page in enumerate(document_ir.pages):
        if page_index == 0:
            section = document.sections[0]
        else:
            section = document.add_section(WD_SECTION.NEW_PAGE)
        _configure_page(section, page)

        regions_by_id = {region.region_id: region for region in page.regions}
        rendered_region_ids: set[str] = set()
        for region_id in page.reading_order:
            region = regions_by_id[region_id]
            if region_id in rendered_region_ids:
                continue
            if region.kind == "text":
                paragraph = document.add_paragraph(_text_for_region(region, translated_text))
                _add_bookmark(paragraph._p, region_id, bookmark_id)
                bookmark_id += 1
            elif region.kind == "checkbox":
                paragraph = document.add_paragraph("☑" if region.checked else "☐")
                _add_bookmark(paragraph._p, region_id, bookmark_id)
                bookmark_id += 1
            elif region.kind == "table":
                cells = [
                    child
                    for child in page.regions
                    if child.parent_region_id == region_id and child.kind == "cell"
                ]
                table = document.add_table(rows=1, cols=max(1, len(cells)))
                for cell_index, cell in enumerate(cells):
                    table_cell = table.cell(0, cell_index)
                    table_cell.text = _text_for_region(cell, translated_text)
                    _add_bookmark(table_cell.paragraphs[0]._p, cell.region_id, bookmark_id)
                    bookmark_id += 1
                    rendered_region_ids.add(cell.region_id)
                _add_bookmark(table._tbl, region_id, bookmark_id)
                bookmark_id += 1
            else:
                raise ValueError(f"unsupported region kind for Cycle 6.2: {region.kind}")
            rendered_region_ids.add(region_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
