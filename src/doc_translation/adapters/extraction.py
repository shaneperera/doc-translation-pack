"""Terra extraction response and conversion into the document IR."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from doc_translation.adapters.normalization import NormalizedPage
from doc_translation.adapters.terra import call_terra
from doc_translation.domain.critical_validation import CriticalToken
from doc_translation.domain.document import DocumentIR, PageGeometry, PageIR
from doc_translation.domain.region import make_region_id


class ExtractionResponse(BaseModel):
    """Structured page and region data returned by Terra."""

    model_config = ConfigDict(extra="forbid")

    pages: list[PageIR]
    language: str | None = None
    critical_tokens: list[CriticalToken] = Field(default_factory=list)
    independent_critical_tokens: list[CriticalToken] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def assign_region_ids(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        payload = deepcopy(value)
        old_to_new: dict[str, str] = {}
        for page_number, page in enumerate(payload.get("pages", []), start=1):
            if not isinstance(page, dict):
                continue
            regions = page.get("regions", [])
            for position, region in enumerate(regions, start=1):
                old_id = region.get("region_id")
                new_id = make_region_id(page_number, position)
                if old_id is not None:
                    old_to_new[old_id] = new_id
                region["region_id"] = new_id
            for region in regions:
                parent_id = region.get("parent_region_id")
                if parent_id is not None:
                    region["parent_region_id"] = old_to_new.get(parent_id)
            geometry = page.get("geometry")
            if isinstance(geometry, dict) and regions:
                geometry["width_points"] = max(
                    float(geometry.get("width_points", 0)),
                    *(region["box"]["x"] + region["box"]["width"] for region in regions),
                )
                geometry["height_points"] = max(
                    float(geometry.get("height_points", 0)),
                    *(region["box"]["y"] + region["box"]["height"] for region in regions),
                )
            page["page_number"] = page_number
            page["reading_order"] = [region["region_id"] for region in regions]
        for key in ("critical_tokens", "independent_critical_tokens"):
            for token in payload.get(key, []):
                token["region_id"] = old_to_new.get(token["region_id"], token["region_id"])
                related_id = token.get("related_region_id")
                if related_id is not None:
                    token["related_region_id"] = old_to_new.get(related_id, related_id)
        return payload


def _pages_in_source_points(
    pages: Sequence[PageIR], normalized_pages: Sequence[NormalizedPage]
) -> list[PageIR]:
    if len(pages) != len(normalized_pages):
        raise ValueError("extracted page count does not match source page count")

    trusted_pages: list[PageIR] = []
    for page, source in zip(pages, normalized_pages, strict=True):
        scale_x = source.width_points / source.width_pixels
        scale_y = source.height_points / source.height_pixels
        regions = []
        for region in page.regions:
            box = region.box
            regions.append(
                region.model_copy(
                    update={
                        "box": box.model_copy(
                            update={
                                "x": box.x * scale_x,
                                "y": box.y * scale_y,
                                "width": box.width * scale_x,
                                "height": box.height * scale_y,
                            }
                        )
                    }
                )
            )
        trusted_pages.append(
            PageIR(
                page_number=source.page_number,
                geometry=PageGeometry(
                    width_points=source.width_points,
                    height_points=source.height_points,
                ),
                rotation=page.rotation,
                language=page.language,
                regions=regions,
                reading_order=page.reading_order,
            )
        )
    return trusted_pages


def extract_document(
    prompt: str,
    source_sha256: str,
    client: Any = None,
) -> DocumentIR:
    """Call Terra and attach the trusted normalized-input hash to its page data."""

    result = call_terra(prompt, ExtractionResponse, client)
    return DocumentIR(
        source_sha256=source_sha256,
        pages=result.parsed.pages,
        language=result.parsed.language,
        critical_tokens=result.parsed.critical_tokens,
        independent_critical_tokens=result.parsed.independent_critical_tokens,
    )


def extract_document_from_rasters(
    prompt: str,
    source_sha256: str,
    normalized_pages: Sequence[NormalizedPage],
    client: Any = None,
) -> DocumentIR:
    """Extract a document from normalized page PNGs sent as multimodal input."""

    result = call_terra(
        prompt,
        ExtractionResponse,
        client,
        [page.path for page in normalized_pages],
    )
    return DocumentIR(
        source_sha256=source_sha256,
        pages=_pages_in_source_points(result.parsed.pages, normalized_pages),
        language=result.parsed.language,
        critical_tokens=result.parsed.critical_tokens,
        independent_critical_tokens=result.parsed.independent_critical_tokens,
    )
