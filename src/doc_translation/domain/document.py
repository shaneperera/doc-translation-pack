"""Validated document and page models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class DocumentIR(BaseModel):
    """Portable ordered description of a document, before translation or DOCX rendering."""

    model_config = ConfigDict(extra="forbid")

    source_sha256: str = Field(min_length=1)
    pages: list[PageIR] = Field(min_length=1)
    language: str | None = None
