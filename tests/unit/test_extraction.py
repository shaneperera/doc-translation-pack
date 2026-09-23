from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from doc_translation.adapters.extraction import (
    ExtractionResponse,
    extract_document,
    extract_document_from_rasters,
)
from doc_translation.adapters.normalization import NormalizedPage
from doc_translation.domain.document import PageGeometry, PageIR
from doc_translation.domain.region import BoundingBox, RegionIR


def _response() -> ExtractionResponse:
    region = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=0, y=0, width=20, height=10),
        source_text="Datum",
    )
    return ExtractionResponse(
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=100, height_points=100),
                regions=[region],
                reading_order=[region.region_id],
            )
        ],
        language="de",
    )


def test_extract_document_uses_trusted_source_hash() -> None:
    client = SimpleNamespace(
        responses=SimpleNamespace(parse=lambda **_: SimpleNamespace(output_parsed=_response()))
    )

    document = extract_document("extract", "source-hash", client)

    assert document.source_sha256 == "source-hash"
    assert document.language == "de"
    assert document.pages[0].regions[0].source_text == "Datum"


def test_extraction_response_rejects_invalid_region() -> None:
    with pytest.raises(ValueError):
        ExtractionResponse.model_validate(
            {
                "pages": [
                    {
                        "page_number": 1,
                        "geometry": {"width_points": 100, "height_points": 100},
                        "regions": [
                            {
                                "region_id": "bad",
                                "kind": "text",
                                "box": {"x": 0, "y": 0, "width": -1, "height": 1},
                            }
                        ],
                        "reading_order": ["bad"],
                    }
                ]
            }
        )


def test_extraction_assigns_stable_ids_and_trusted_point_geometry(tmp_path: Path) -> None:
    raster = tmp_path / "page.png"
    raster.write_bytes(b"raster")
    response = ExtractionResponse.model_validate(
        {
            "pages": [
                {
                    "page_number": 9,
                    "geometry": {"width_points": 50, "height_points": 50},
                    "regions": [
                        {
                            "region_id": "model-id",
                            "kind": "text",
                            "box": {"x": 20, "y": 40, "width": 100, "height": 200},
                        }
                    ],
                    "reading_order": ["model-id"],
                }
            ]
        }
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(
            parse=lambda **_: SimpleNamespace(output_parsed=response)
        )
    )
    source_page = NormalizedPage(
        page_number=1,
        path=raster,
        width_pixels=200,
        height_pixels=400,
        width_points=72,
        height_points=144,
        dpi_x=200,
        dpi_y=200,
        dpi_assumed=False,
    )

    document = extract_document_from_rasters(
        "extract", "source-hash", [source_page], client
    )

    page = document.pages[0]
    assert page.geometry == PageGeometry(width_points=72, height_points=144)
    assert page.regions[0].region_id == "p0001-r0001"
    assert page.reading_order == ["p0001-r0001"]
    assert page.regions[0].box.model_dump() == pytest.approx(
        {
            "x": 7.2,
            "y": 14.4,
            "width": 36.0,
            "height": 72.0,
        }
    )
