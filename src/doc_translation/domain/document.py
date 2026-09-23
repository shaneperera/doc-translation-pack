"""Validated document and page models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from doc_translation.domain.region import RegionIR


class PageGeometry(BaseModel):
    """Physical page dimensions in PDF points (72 points per inch)."""

    model_config = ConfigDict(extra="forbid")

    width_points: float = Field(gt=0)
    height_points: float = Field(gt=0)


class PageIR(BaseModel):
    """Logical page metadata shared after rasterization and before OCR/translation."""

    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1)
    geometry: PageGeometry
    rotation: Literal[0, 90, 180, 270] = 0
    language: str | None = None
    regions: list[RegionIR] = Field(default_factory=list)
    reading_order: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_regions(self) -> PageIR:
        region_ids = [region.region_id for region in self.regions]
        if len(region_ids) != len(set(region_ids)):
            raise ValueError("region IDs must be unique within a page")

        expected_order = set(region_ids)
        if (
            len(self.reading_order) != len(expected_order)
            or set(self.reading_order) != expected_order
        ):
            raise ValueError("reading order must contain every region exactly once")

        page_prefix = f"p{self.page_number:04d}-"
        for region in self.regions:
            if not region.region_id.startswith(page_prefix):
                raise ValueError("region ID page does not match its containing page")
            if (
                region.parent_region_id is not None
                and region.parent_region_id not in expected_order
            ):
                raise ValueError("region parent must exist on the same page")
            if region.box.x + region.box.width > self.geometry.width_points:
                raise ValueError("region extends beyond page width")
            if region.box.y + region.box.height > self.geometry.height_points:
                raise ValueError("region extends beyond page height")
        return self


class DocumentIR(BaseModel):
    """Portable ordered description of a document, before translation or DOCX rendering."""

    model_config = ConfigDict(extra="forbid")

    source_sha256: str = Field(min_length=1)
    pages: list[PageIR] = Field(min_length=1)
    language: str | None = None

    @model_validator(mode="after")
    def validate_pages(self) -> DocumentIR:
        page_numbers = [page.page_number for page in self.pages]
        if page_numbers != list(range(1, len(self.pages) + 1)):
            raise ValueError("pages must be ordered and numbered consecutively")

        region_ids = [region.region_id for page in self.pages for region in page.regions]
        if len(region_ids) != len(set(region_ids)):
            raise ValueError("region IDs must be unique within a document")
        return self
