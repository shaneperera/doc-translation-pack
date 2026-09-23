"""Minimal native DOCX rendering for text regions."""

from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches
from docx.text.paragraph import Paragraph
from lxml import etree  # type: ignore[import-untyped]
from PIL import Image

from doc_translation.domain.document import DocumentIR, PageIR

DEFAULT_FONT_SIZE = 11
MIN_FONT_SIZE = 7


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


def _fit_font_size(text: str, width_points: float, height_points: float) -> int:
    for font_size in range(DEFAULT_FONT_SIZE, MIN_FONT_SIZE - 1, -1):
        characters_per_line = max(1, int(width_points / (font_size * 0.5)))
        lines = text.splitlines() or [""]
        longest_line = max(len(line) for line in lines)
        if longest_line <= characters_per_line and len(lines) * font_size * 1.2 <= height_points:
            return font_size
    return MIN_FONT_SIZE


WPS_NS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"


def _wps_element(name: str) -> etree._Element:
    return etree.Element(f"{{{WPS_NS}}}{name}")


def _add_text_box(
    paragraph: object,
    text: str,
    rotation: float,
    width_points: float,
    height_points: float,
    font_size: int,
) -> None:
    inline = OxmlElement("wp:inline")
    extent = OxmlElement("wp:extent")
    extent.set("cx", str(round(width_points * 12_700)))
    extent.set("cy", str(round(height_points * 12_700)))
    inline.append(extent)

    graphic = OxmlElement("a:graphic")
    graphic_data = OxmlElement("a:graphicData")
    graphic_data.set("uri", "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup")
    shape = _wps_element("wsp")
    shape_properties = _wps_element("spPr")
    transform = OxmlElement("a:xfrm")
    transform.set("rot", str(round(rotation * 60_000)))
    shape_properties.append(transform)
    shape.append(shape_properties)
    text_box = _wps_element("txbx")
    text_content = OxmlElement("w:txbxContent")
    text_paragraph = OxmlElement("w:p")
    text_run = OxmlElement("w:r")
    run_properties = OxmlElement("w:rPr")
    size = OxmlElement("w:sz")
    size.set(qn("w:val"), str(font_size * 2))
    run_properties.append(size)
    text_run.append(run_properties)
    text_node = OxmlElement("w:t")
    text_node.text = text
    text_run.append(text_node)
    text_paragraph.append(text_run)
    text_content.append(text_paragraph)
    text_box.append(text_content)
    shape.append(text_box)
    graphic_data.append(shape)
    graphic.append(graphic_data)
    inline.append(graphic)
    paragraph.add_run()._r.append(inline)  # type: ignore[attr-defined]


def _add_image_mark(
    document: DocumentObject, page: PageIR, region: object, raster_path: Path
) -> Paragraph:
    with Image.open(raster_path) as image:
        box = region.box  # type: ignore[attr-defined]
        left = round(box.x / page.geometry.width_points * image.width)
        top = round(box.y / page.geometry.height_points * image.height)
        right = round((box.x + box.width) / page.geometry.width_points * image.width)
        bottom = round((box.y + box.height) / page.geometry.height_points * image.height)
        crop = image.crop((left, top, right, bottom))
        stream = BytesIO()
        crop.save(stream, format="PNG")
        stream.seek(0)
        paragraph: Paragraph = document.add_paragraph()
        paragraph.add_run().add_picture(
            stream,
            width=Inches(box.width / 72),
            height=Inches(box.height / 72),
        )
        return paragraph


def render_text_docx(
    document_ir: DocumentIR,
    translated_text: Mapping[str, str],
    output_path: Path,
    page_rasters: Mapping[int, Path] | None = None,
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
                text = _text_for_region(region, translated_text)
                font_size = _fit_font_size(text, region.box.width, region.box.height)
                if font_size == MIN_FONT_SIZE:
                    lines = text.splitlines() or [""]
                    characters_per_line = max(1, int(region.box.width / (MIN_FONT_SIZE * 0.5)))
                    too_wide = max(len(line) for line in lines) > characters_per_line
                    too_tall = len(lines) * MIN_FONT_SIZE * 1.2 > region.box.height
                    if too_wide or too_tall:
                        raise ValueError(f"text does not fit at 7 pt: {region_id}")
                paragraph = document.add_paragraph()
                _add_text_box(
                    paragraph,
                    text,
                    region.rotation,
                    region.box.width,
                    region.box.height,
                    font_size,
                )
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
            elif region.kind == "image_mark":
                if page_rasters is None or page.page_number not in page_rasters:
                    raise ValueError(f"missing raster for image mark: {region_id}")
                paragraph = _add_image_mark(
                    document,
                    page,
                    region,
                    page_rasters[page.page_number],
                )
                _add_bookmark(paragraph._p, region_id, bookmark_id)
                bookmark_id += 1
            else:
                raise ValueError(f"unsupported region kind for Cycle 6.2: {region.kind}")
            rendered_region_ids.add(region_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
