"""Shared translation use case for CLI and UI callers."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from doc_translation.adapters.docx import expand_text_regions, render_text_docx
from doc_translation.adapters.docx_validation import validate_docx_for_publication
from doc_translation.adapters.extraction import extract_document_from_rasters
from doc_translation.adapters.normalization import normalize_input
from doc_translation.adapters.terra import TERRA_MODEL
from doc_translation.adapters.translation import translate_regions
from doc_translation.domain.content_validation import validate_content
from doc_translation.domain.critical_validation import (
    compare_critical_tokens,
    validate_special_regions,
)
from doc_translation.domain.region import RegionIR

EXTRACTION_PROMPT = (
    "Extract every visible page region into the supplied schema. "
    "Report every bounding box in source-raster pixels from the top-left corner. "
    "Set page geometry width_points and height_points to the raster pixel dimensions; "
    "trusted physical dimensions replace them after extraction. "
    "Use one region per independently positioned text span, table cell, checkbox, line, "
    "image mark, or confirmed watermark, and return regions in reading order. "
    "Tables are grouping regions only. "
    "Set translation_eligible=false for tables, checkboxes, lines, image marks, confirmed "
    "watermarks, and already-English spans."
)
TRANSLATION_BATCH_SIZE = 10


def _translation_prompt(
    document_language: str | None, target_language: str, regions: Sequence[RegionIR]
) -> str:
    source_language = document_language or "detected source language"
    lines = [
        f"Translate eligible region text from {source_language} to {target_language}.",
        "Return one translation for every eligible region ID and preserve immutable tokens.",
        "Use concise wording that fits the source box and preserve explicit line breaks.",
        "Copy every immutable token exactly as written, including its Unicode character form.",
    ]
    for region in regions:
        if region.translation_eligible:
            lines.append(
                f"{region.region_id} ({region.box.width:g}x{region.box.height:g} pt): "
                f"{region.source_text or ''}"
            )
    return "\n".join(lines)


def translate_input(
    source: Path,
    output: Path,
    target_language: str = "en",
    source_language: str | None = None,
    client: Any = None,
    force: bool = False,
) -> None:
    """Run the current translation stages and publish only after validation succeeds."""

    if output.exists() and not force:
        raise FileExistsError(output)
    audit_output = output.with_suffix(".audit.json")
    if audit_output.exists() and not force:
        raise FileExistsError(audit_output)

    with TemporaryDirectory(prefix="doc-translation-") as directory:
        work_dir = Path(directory)
        normalized = normalize_input(source, work_dir / "rasters")
        document = extract_document_from_rasters(
            EXTRACTION_PROMPT,
            normalized.source_sha256,
            normalized.pages,
            client,
        )
        if source_language is not None:
            document = document.model_copy(update={"language": source_language})
        regions = [region for page in document.pages for region in page.regions]
        translations: dict[str, str] = {}
        eligible_regions = [region for region in regions if region.translation_eligible]
        for start in range(0, len(eligible_regions), TRANSLATION_BATCH_SIZE):
            batch = eligible_regions[start : start + TRANSLATION_BATCH_SIZE]
            translations.update(
                translate_regions(
                    _translation_prompt(document.language, target_language, batch),
                    batch,
                    client,
                )
            )
        delivered_text = {
            region.region_id: translations.get(region.region_id, region.source_text or "")
            for region in regions
        }
        validation = validate_content(regions, delivered_text, document.language)
        diagnostics = list(validation.diagnostics)
        omitted_watermark_ids = {
            region.region_id for region in regions if region.kind == "watermark"
        }
        diagnostics.extend(
            compare_critical_tokens(
                document.critical_tokens,
                document.independent_critical_tokens,
            )
        )
        diagnostics.extend(
            validate_special_regions(regions, delivered_text, omitted_watermark_ids)
        )
        if diagnostics:
            details = "; ".join(
                f"{item.code}:{item.region_id or 'document'}:{item.expected or ''}"
                for item in diagnostics
            )
            raise ValueError(f"content validation failed: {details}")
        rendered = work_dir / "translated.docx"
        rendered_document = document
        for fit_attempt in range(3):
            try:
                layout_document = expand_text_regions(document, translations)
                rendered_document = render_text_docx(
                    layout_document,
                    translations,
                    rendered,
                    {page.page_number: page.path for page in normalized.pages},
                )
                break
            except ValueError as error:
                marker = "text does not fit at "
                if marker not in str(error) or fit_attempt == 2:
                    raise
                region_id = str(error).rsplit(": ", 1)[-1]
                source_region = next(
                    region
                    for page in layout_document.pages
                    for region in page.regions
                    if region.region_id == region_id
                )
                retry_prompt = (
                    f"{_translation_prompt(document.language, target_language, [source_region])}\n"
                    f"The current translation for {region_id} does not fit its "
                    f"{source_region.box.width:g}x{source_region.box.height:g} point box. "
                    "Return a shorter faithful translation for that region. "
                    "Preserve every immutable token exactly and retain source line breaks."
                )
                corrected = translate_regions(retry_prompt, [source_region], client)
                translations.update(corrected)
        validate_docx_for_publication(
            rendered,
            rendered_document.pages,
            work_dir / "publication-validation",
        )
        rendered_regions_by_id = {
            region.region_id: region
            for page in rendered_document.pages
            for region in page.regions
        }
        audit = {
            "source_sha256": document.source_sha256,
            "target_language": target_language,
            "model": TERRA_MODEL,
            "omitted_watermark_region_ids": sorted(omitted_watermark_ids),
            "regions": [
                {
                    "region_id": region.region_id,
                    "source_text": region.source_text,
                    "translated_text": delivered_text[region.region_id],
                    "geometry": rendered_regions_by_id[region.region_id].box.model_dump(),
                    "status": "validated",
                }
                for region in regions
            ],
        }
        audit_path = work_dir / "translated.audit.json"
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2))
        output.parent.mkdir(parents=True, exist_ok=True)
        os.replace(rendered, output)
        os.replace(audit_path, audit_output)
