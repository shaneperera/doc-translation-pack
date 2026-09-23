"""Shared translation use case for CLI and UI callers."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from doc_translation.adapters.docx import render_text_docx
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


def _translation_prompt(
    document_language: str | None, target_language: str, regions: Sequence[RegionIR]
) -> str:
    source_language = document_language or "detected source language"
    lines = [
        f"Translate eligible region text from {source_language} to {target_language}.",
        "Return one translation for every eligible region ID and preserve immutable tokens.",
    ]
    for region in regions:
        if region.translation_eligible:
            lines.append(f"{region.region_id}: {region.source_text or ''}")
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
            "Extract every visible page region into the supplied schema.",
            normalized.source_sha256,
            [page.path for page in normalized.pages],
            client,
        )
        if source_language is not None:
            document = document.model_copy(update={"language": source_language})
        regions = [region for page in document.pages for region in page.regions]
        translations = translate_regions(
            _translation_prompt(document.language, target_language, regions),
            regions,
            client,
        )
        delivered_text = {
            region.region_id: translations.get(region.region_id, region.source_text or "")
            for region in regions
        }
        validation = validate_content(regions, delivered_text, document.language)
        diagnostics = list(validation.diagnostics)
        diagnostics.extend(
            compare_critical_tokens(
                document.critical_tokens,
                document.independent_critical_tokens,
            )
        )
        diagnostics.extend(validate_special_regions(regions, delivered_text, set()))
        if diagnostics:
            raise ValueError("content validation failed")
        rendered = work_dir / "translated.docx"
        render_text_docx(
            document,
            translations,
            rendered,
            {page.page_number: page.path for page in normalized.pages},
        )
        audit = {
            "source_sha256": document.source_sha256,
            "target_language": target_language,
            "model": TERRA_MODEL,
            "regions": [
                {
                    "region_id": region.region_id,
                    "source_text": region.source_text,
                    "translated_text": delivered_text[region.region_id],
                    "geometry": region.box.model_dump(),
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
