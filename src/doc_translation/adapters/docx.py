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
from docx.shared import Inches, Pt
from docx.text.paragraph import Paragraph
from lxml import etree  # type: ignore[import-untyped]
from PIL import Image

from doc_translation.domain.document import DocumentIR, PageIR

DEFAULT_FONT_SIZE = 11
MIN_FONT_SIZE = 5


def _configure_page(section: object, page: PageIR) -> None:
    width_inches = page.geometry.width_points / 72
    height_inches = page.geometry.height_points / 72
    section.page_width = Inches(width_inches)  # type: ignore[attr-defined]
    section.page_height = Inches(height_inches)  # type: ignore[attr-defined]
    if width_inches > height_inches:
        section.orientation = WD_ORIENT.LANDSCAPE  # type: ignore[attr-defined]
    else:
        section.orientation = WD_ORIENT.PORTRAIT  # type: ignore[attr-defined]
    section.top_margin = Inches(0)  # type: ignore[attr-defined]
    section.bottom_margin = Inches(0)  # type: ignore[attr-defined]
    section.left_margin = Inches(0)  # type: ignore[attr-defined]
    section.right_margin = Inches(0)  # type: ignore[attr-defined]


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


def _positioned_anchor(
    x_points: float,
    y_points: float,
    width_points: float,
    height_points: float,
    drawing_id: int,
) -> etree._Element:
    anchor = OxmlElement("wp:anchor")
    for name, value in {
        "distT": "0",
        "distB": "0",
        "distL": "0",
        "distR": "0",
        "simplePos": "0",
        "relativeHeight": str(drawing_id),
        "behindDoc": "0",
        "locked": "0",
        "layoutInCell": "1",
        "allowOverlap": "1",
    }.items():
        anchor.set(name, value)
    simple_position = OxmlElement("wp:simplePos")
    simple_position.set("x", "0")
    simple_position.set("y", "0")
    anchor.append(simple_position)
    for axis, offset in (("H", x_points), ("V", y_points)):
        position = OxmlElement(f"wp:position{axis}")
        position.set("relativeFrom", "page")
        position_offset = OxmlElement("wp:posOffset")
        position_offset.text = str(round(offset * 12_700))
        position.append(position_offset)
        anchor.append(position)
    extent = OxmlElement("wp:extent")
    extent.set("cx", str(round(width_points * 12_700)))
    extent.set("cy", str(round(height_points * 12_700)))
    anchor.append(extent)
    effect_extent = OxmlElement("wp:effectExtent")
    for side in ("l", "t", "r", "b"):
        effect_extent.set(side, "0")
    anchor.append(effect_extent)
    anchor.append(OxmlElement("wp:wrapNone"))
    properties = OxmlElement("wp:docPr")
    properties.set("id", str(drawing_id))
    properties.set("name", f"Region {drawing_id}")
    anchor.append(properties)
    anchor.append(OxmlElement("wp:cNvGraphicFramePr"))
    return anchor


def _add_positioned_shape(
    paragraph: object,
    text: str | None,
    rotation: float,
    x_points: float,
    y_points: float,
    width_points: float,
    height_points: float,
    font_size: int,
    drawing_id: int,
    border: bool = False,
    black_fill: bool = False,
) -> object:
    anchor = _positioned_anchor(
        x_points,
        y_points,
        width_points,
        height_points,
        drawing_id,
    )

    graphic = OxmlElement("a:graphic")
    graphic_data = OxmlElement("a:graphicData")
    graphic_data.set("uri", WPS_NS)
    shape = _wps_element("wsp")
    shape.append(_wps_element("cNvSpPr"))
    shape_properties = _wps_element("spPr")
    transform = OxmlElement("a:xfrm")
    transform.set("rot", str(round(rotation * 60_000)))
    shape_properties.append(transform)
    geometry = OxmlElement("a:prstGeom")
    geometry.set("prst", "rect")
    geometry.append(OxmlElement("a:avLst"))
    shape_properties.append(geometry)
    if black_fill:
        fill = OxmlElement("a:solidFill")
        colour = OxmlElement("a:srgbClr")
        colour.set("val", "000000")
        fill.append(colour)
        shape_properties.append(fill)
    else:
        shape_properties.append(OxmlElement("a:noFill"))
    line = OxmlElement("a:ln")
    line.set("w", "12700")
    if border:
        line_fill = OxmlElement("a:solidFill")
        line_colour = OxmlElement("a:srgbClr")
        line_colour.set("val", "000000")
        line_fill.append(line_colour)
        line.append(line_fill)
    else:
        line.append(OxmlElement("a:noFill"))
    shape_properties.append(line)
    shape.append(shape_properties)
    if text is not None:
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
        body_properties = _wps_element("bodyPr")
        for inset in ("lIns", "tIns", "rIns", "bIns"):
            body_properties.set(inset, "0")
        shape.append(body_properties)
    graphic_data.append(shape)
    graphic.append(graphic_data)
    anchor.append(graphic)
    drawing = OxmlElement("w:drawing")
    drawing.append(anchor)
    run = paragraph.add_run()  # type: ignore[attr-defined]
    run._r.append(drawing)
    return run._r


def _add_image_mark(
    paragraph: Paragraph,
    page: PageIR,
    region: object,
    raster_path: Path,
    drawing_id: int,
) -> object:
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
        run = paragraph.add_run()
        run.add_picture(
            stream,
            width=Inches(box.width / 72),
            height=Inches(box.height / 72),
        )
        inline = run._r.find(qn("w:drawing")).find(qn("wp:inline"))
        inline.tag = qn("wp:anchor")
        for name, value in {
            "distT": "0",
            "distB": "0",
            "distL": "0",
            "distR": "0",
            "simplePos": "0",
            "relativeHeight": str(drawing_id),
            "behindDoc": "0",
            "locked": "0",
            "layoutInCell": "1",
            "allowOverlap": "1",
        }.items():
            inline.set(name, value)
        simple_position = OxmlElement("wp:simplePos")
        simple_position.set("x", "0")
        simple_position.set("y", "0")
        inline.insert(0, simple_position)
        for index, (axis, offset) in enumerate(
            (("H", box.x), ("V", box.y)), start=1
        ):
            position = OxmlElement(f"wp:position{axis}")
            position.set("relativeFrom", "page")
            position_offset = OxmlElement("wp:posOffset")
            position_offset.text = str(round(offset * 12_700))
            position.append(position_offset)
            inline.insert(index, position)
        effect_extent = inline.find(qn("wp:effectExtent"))
        if effect_extent is None:
            extent = inline.find(qn("wp:extent"))
            wrap_index = list(inline).index(extent) + 1
        else:
            wrap_index = list(inline).index(effect_extent) + 1
        inline.insert(wrap_index, OxmlElement("wp:wrapNone"))
        return run._r


def _font_size_or_raise(text: str, region: object) -> int:
    box = region.box  # type: ignore[attr-defined]
    font_size = _fit_font_size(text, box.width, box.height)
    if font_size == MIN_FONT_SIZE:
        lines = text.splitlines() or [""]
        characters_per_line = max(1, int(box.width / (MIN_FONT_SIZE * 0.5)))
        too_wide = max(len(line) for line in lines) > characters_per_line
        too_tall = len(lines) * MIN_FONT_SIZE * 1.2 > box.height
        if too_wide or too_tall:
            raise ValueError(
                f"text does not fit at {MIN_FONT_SIZE} pt: {region.region_id}"  # type: ignore[attr-defined]
            )
    return font_size


def expand_text_regions(
    document_ir: DocumentIR, translated_text: Mapping[str, str]
) -> DocumentIR:
    pages: list[PageIR] = []
    for page in document_ir.pages:
        regions = []
        regions_by_id = {region.region_id: region for region in page.regions}
        for region in page.regions:
            text = _text_for_region(region, translated_text)
            if region.kind not in {"text", "cell"} or region.rotation not in {0, 180}:
                regions.append(region)
                continue
            try:
                _font_size_or_raise(text, region)
                regions.append(region)
                continue
            except ValueError:
                pass

            right_edge = page.geometry.width_points
            if region.parent_region_id in regions_by_id:
                parent = regions_by_id[region.parent_region_id]
                right_edge = min(right_edge, parent.box.x + parent.box.width)
            region_bottom = region.box.y + region.box.height
            overlaps_existing_region = False
            for other in page.regions:
                if other.region_id == region.region_id or other.kind in {
                    "table",
                    "watermark",
                }:
                    continue
                if other.region_id == region.parent_region_id:
                    continue
                other_bottom = other.box.y + other.box.height
                overlaps_vertically = region.box.y < other_bottom and other.box.y < region_bottom
                if not overlaps_vertically:
                    continue
                other_right = other.box.x + other.box.width
                if other.box.x < region.box.x + region.box.width and other_right > region.box.x:
                    overlaps_existing_region = True
                    break
                if other.box.x >= region.box.x + region.box.width:
                    right_edge = min(right_edge, other.box.x)

            expanded_width = (
                region.box.width
                if overlaps_existing_region
                else max(region.box.width, right_edge - region.box.x)
            )
            regions.append(
                region.model_copy(
                    update={
                        "box": region.box.model_copy(update={"width": expanded_width})
                    }
                )
            )
        pages.append(page.model_copy(update={"regions": regions}))
    return document_ir.model_copy(update={"pages": pages})


def _page_host(document: DocumentObject) -> Paragraph:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = Pt(1)
    return paragraph


def render_text_docx(
    document_ir: DocumentIR,
    translated_text: Mapping[str, str],
    output_path: Path,
    page_rasters: Mapping[int, Path] | None = None,
) -> DocumentIR:
    """Render supported regions as editable Word content with source page sizes."""

    document_ir = expand_text_regions(document_ir, translated_text)
    document = Document()
    bookmark_id = 1
    for page_index, page in enumerate(document_ir.pages):
        if page_index == 0:
            section = document.sections[0]
        else:
            section = document.add_section(WD_SECTION.NEW_PAGE)
        _configure_page(section, page)
        host = _page_host(document)

        regions_by_id = {region.region_id: region for region in page.regions}
        for region_id in page.reading_order:
            region = regions_by_id[region_id]
            if region.kind in {"text", "cell"}:
                text = _text_for_region(region, translated_text)
                run = _add_positioned_shape(
                    host,
                    text,
                    region.rotation,
                    region.box.x,
                    region.box.y,
                    region.box.width,
                    region.box.height,
                    _font_size_or_raise(text, region),
                    bookmark_id,
                    border=region.kind == "cell",
                )
                _add_bookmark(run, region_id, bookmark_id)
                bookmark_id += 1
            elif region.kind == "checkbox":
                run = _add_positioned_shape(
                    host,
                    "☑" if region.checked else "☐",
                    region.rotation,
                    region.box.x,
                    region.box.y,
                    region.box.width,
                    region.box.height,
                    _font_size_or_raise("☑", region),
                    bookmark_id,
                )
                _add_bookmark(run, region_id, bookmark_id)
                bookmark_id += 1
            elif region.kind == "table":
                continue
            elif region.kind == "line":
                width = region.box.width
                height = region.box.height
                if width >= height:
                    height = min(height, 1)
                else:
                    width = min(width, 1)
                run = _add_positioned_shape(
                    host,
                    None,
                    region.rotation,
                    region.box.x,
                    region.box.y,
                    width,
                    height,
                    MIN_FONT_SIZE,
                    bookmark_id,
                    black_fill=True,
                )
                _add_bookmark(run, region_id, bookmark_id)
                bookmark_id += 1
            elif region.kind == "image_mark":
                if page_rasters is None or page.page_number not in page_rasters:
                    raise ValueError(f"missing raster for image mark: {region_id}")
                run = _add_image_mark(
                    host,
                    page,
                    region,
                    page_rasters[page.page_number],
                    bookmark_id,
                )
                _add_bookmark(run, region_id, bookmark_id)
                bookmark_id += 1
            elif region.kind == "watermark":
                continue
            else:
                raise ValueError(f"unsupported region kind: {region.kind}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
    return document_ir
