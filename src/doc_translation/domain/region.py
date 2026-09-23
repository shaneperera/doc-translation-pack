"""Validated page-region models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RegionKind = Literal[
    "text",
    "table",
    "cell",
    "checkbox",
    "line",
    "image_mark",
    "watermark",
]


class BoundingBox(BaseModel):
    """A region rectangle in page points, measured from the top-left corner."""

    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(ge=0)
    height: float = Field(ge=0)


class RegionIR(BaseModel):
    """One generic visible page region, independent of document type or filename."""

    model_config = ConfigDict(extra="forbid")

    region_id: str = Field(pattern=r"^p\d{4}-r\d{4}$")
    kind: RegionKind
    box: BoundingBox
    rotation: Literal[0, 90, 180, 270] = 0
    source_text: str | None = None
    translation_eligible: bool = True
    immutable_tokens: list[str] = Field(default_factory=list)
    unreadable: bool = False
    parent_region_id: str | None = None
    checked: bool = False


def make_region_id(page_number: int, reading_order_position: int) -> str:
    """Create the stable ID for a page and its one-based reading-order position."""

    if page_number < 1 or reading_order_position < 1:
        raise ValueError("page number and reading-order position must be positive")
    return f"p{page_number:04d}-r{reading_order_position:04d}"
