from __future__ import annotations

import pytest
from pydantic import ValidationError

from doc_translation.domain.document import DocumentIR, PageGeometry, PageIR
from doc_translation.domain.region import BoundingBox, RegionIR, make_region_id


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


def test_regions_support_columns_nested_tables_and_rotated_headers() -> None:
    prose = RegionIR(
        region_id=make_region_id(1, 1),
        kind="text",
        box=BoundingBox(x=20, y=20, width=250, height=40),
        source_text="Patient details",
    )
    second_column = RegionIR(
        region_id=make_region_id(1, 2),
        kind="text",
        box=BoundingBox(x=300, y=20, width=200, height=40),
        source_text="Visit details",
    )
    table = RegionIR(
        region_id=make_region_id(1, 3),
        kind="table",
        box=BoundingBox(x=20, y=80, width=500, height=300),
        translation_eligible=False,
    )
    cell = RegionIR(
        region_id=make_region_id(1, 4),
        kind="cell",
        box=BoundingBox(x=20, y=80, width=250, height=100),
        parent_region_id=table.region_id,
    )
    rotated_header = RegionIR(
        region_id=make_region_id(1, 5),
        kind="text",
        box=BoundingBox(x=530, y=20, width=40, height=200),
        rotation=90,
        source_text="Date",
        immutable_tokens=["2026"],
    )

    page = PageIR(
        page_number=1,
        geometry=PageGeometry(width_points=600, height_points=800),
        regions=[prose, second_column, table, cell, rotated_header],
        reading_order=[
            prose.region_id,
            second_column.region_id,
            table.region_id,
            cell.region_id,
            rotated_header.region_id,
        ],
    )

    assert page.regions[3].parent_region_id == table.region_id
    assert page.regions[4].rotation == 90


def test_page_rejects_duplicate_ids_and_incomplete_reading_order() -> None:
    region = RegionIR(
        region_id=make_region_id(1, 1),
        kind="text",
        box=BoundingBox(x=0, y=0, width=10, height=10),
    )

    with pytest.raises(ValidationError):
        PageIR(
            page_number=1,
            geometry=PageGeometry(width_points=100, height_points=100),
            regions=[region, region],
            reading_order=[region.region_id],
        )

    with pytest.raises(ValidationError):
        PageIR(
            page_number=1,
            geometry=PageGeometry(width_points=100, height_points=100),
            regions=[region],
            reading_order=[],
        )


def test_page_rejects_broken_parent_and_out_of_bounds_region() -> None:
    with pytest.raises(ValidationError):
        PageIR(
            page_number=1,
            geometry=PageGeometry(width_points=100, height_points=100),
            regions=[
                RegionIR(
                    region_id=make_region_id(1, 1),
                    kind="cell",
                    box=BoundingBox(x=0, y=0, width=10, height=10),
                    parent_region_id=make_region_id(1, 2),
                )
            ],
            reading_order=[make_region_id(1, 1)],
        )

    with pytest.raises(ValidationError):
        PageIR(
            page_number=1,
            geometry=PageGeometry(width_points=100, height_points=100),
            regions=[
                RegionIR(
                    region_id=make_region_id(1, 1),
                    kind="text",
                    box=BoundingBox(x=95, y=0, width=10, height=10),
                )
            ],
            reading_order=[make_region_id(1, 1)],
        )


def test_region_id_generation_is_deterministic() -> None:
    assert make_region_id(2, 3) == "p0002-r0003"

    with pytest.raises(ValueError):
        make_region_id(0, 1)
