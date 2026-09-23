from __future__ import annotations

from types import SimpleNamespace

import pytest

from doc_translation.adapters.extraction import ExtractionResponse, extract_document
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
                                "box": {"x": 0, "y": 0, "width": 1, "height": 1},
                            }
                        ],
                        "reading_order": ["bad"],
                    }
                ]
            }
        )
