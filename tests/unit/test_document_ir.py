from __future__ import annotations

import pytest
from pydantic import ValidationError

from doc_translation.domain.document import DocumentIR, PageGeometry, PageIR


def test_document_ir_round_trips_through_json() -> None:
    document = DocumentIR(
        source_sha256="abc123",
        language="de",
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=612, height_points=792),
                rotation=90,
                language="de",
            )
        ],
    )

    restored = DocumentIR.model_validate_json(document.model_dump_json())

    assert restored == document


@pytest.mark.parametrize(
    "value",
    [
        {"width_points": 0, "height_points": 100},
        {"width_points": 100, "height_points": -1},
    ],
)
def test_page_geometry_rejects_non_positive_dimensions(value: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        PageGeometry(**value)


def test_page_rejects_invalid_rotation() -> None:
    with pytest.raises(ValidationError):
        PageIR(
            page_number=1,
            geometry=PageGeometry(width_points=100, height_points=100),
            rotation=45,  # type: ignore[arg-type]
        )


def test_document_rejects_empty_pages() -> None:
    with pytest.raises(ValidationError):
        DocumentIR(source_sha256="abc123", pages=[])
