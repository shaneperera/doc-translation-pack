from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from pydantic import BaseModel

from doc_translation.adapters.extraction import ExtractionResponse
from doc_translation.adapters.translation import TranslationResponse
from doc_translation.domain.document import PageGeometry, PageIR
from doc_translation.domain.region import BoundingBox, RegionIR
from doc_translation.pipeline.service import translate_input


def test_translate_input_publishes_validated_docx(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (200, 200), "white").save(source)
    output = tmp_path / "output.docx"
    region = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=0, y=0, width=100, height=20),
        source_text="Hallo",
    )
    extraction = ExtractionResponse(
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

    def parse(*, text_format: type[BaseModel], **_: object) -> SimpleNamespace:
        if text_format is ExtractionResponse:
            return SimpleNamespace(output_parsed=extraction)
        return SimpleNamespace(
            output_parsed=TranslationResponse(translations={region.region_id: "Hello"})
        )

    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    translate_input(source, output, client=client)

    assert output.is_file()
