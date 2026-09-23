from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from pydantic import BaseModel

from doc_translation.adapters.extraction import ExtractionResponse
from doc_translation.adapters.translation import TranslationItem, TranslationResponse
from doc_translation.domain.document import PageGeometry, PageIR
from doc_translation.domain.region import BoundingBox, RegionIR
from doc_translation.pipeline.service import translate_input


@pytest.fixture(autouse=True)
def allow_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "doc_translation.pipeline.service.validate_docx_for_publication",
        lambda *_: None,
    )


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
    watermark = RegionIR(
        region_id="p0001-r0002",
        kind="watermark",
        box=BoundingBox(x=0, y=30, width=100, height=20),
        source_text="COPY",
        translation_eligible=False,
    )
    extraction = ExtractionResponse(
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=100, height_points=100),
                regions=[region, watermark],
                reading_order=[region.region_id, watermark.region_id],
            )
        ],
        language="de",
    )

    def parse(*, text_format: type[BaseModel], **_: object) -> SimpleNamespace:
        if text_format is ExtractionResponse:
            return SimpleNamespace(output_parsed=extraction)
        return SimpleNamespace(
            output_parsed=TranslationResponse(
                translations=[TranslationItem(region_id=region.region_id, text="Hello")]
            )
        )

    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    translate_input(source, output, client=client)

    assert output.is_file()
    audit = json.loads(output.with_suffix(".audit.json").read_text())
    assert audit["source_sha256"]
    assert audit["model"] == "gpt-5.6-terra"
    assert audit["regions"][0]["translated_text"] == "Hello"
    assert audit["omitted_watermark_region_ids"] == [watermark.region_id]


def test_translate_input_leaves_output_absent_when_extraction_fails(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (20, 20), "white").save(source)
    output = tmp_path / "output.docx"

    def parse(**_: object) -> SimpleNamespace:
        raise RuntimeError("model failure")

    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))

    try:
        translate_input(source, output, client=client)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected model failure")

    assert not output.exists()


def test_translate_input_refuses_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (20, 20), "white").save(source)
    output = tmp_path / "output.docx"
    output.write_text("old")

    try:
        translate_input(source, output)
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected existing-output refusal")

    assert output.read_text() == "old"


def test_translate_input_leaves_output_absent_when_translation_fails(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (20, 20), "white").save(source)
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
        ]
    )

    def parse(*, text_format: type[BaseModel], **_: object) -> SimpleNamespace:
        if text_format is ExtractionResponse:
            return SimpleNamespace(output_parsed=extraction)
        return SimpleNamespace(output_parsed=TranslationResponse(translations=[]))

    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    with pytest.raises(ValueError):
        translate_input(source, output, client=client)

    assert not output.exists()


def test_translate_input_does_not_publish_when_publication_gate_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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
                geometry=PageGeometry(width_points=200, height_points=200),
                regions=[region],
                reading_order=[region.region_id],
            )
        ]
    )

    def parse(*, text_format: type[BaseModel], **_: object) -> SimpleNamespace:
        if text_format is ExtractionResponse:
            return SimpleNamespace(output_parsed=extraction)
        return SimpleNamespace(
            output_parsed=TranslationResponse(
                translations=[TranslationItem(region_id=region.region_id, text="Hello")]
            )
        )

    monkeypatch.setattr(
        "doc_translation.pipeline.service.validate_docx_for_publication",
        lambda *_: (_ for _ in ()).throw(ValueError("page count mismatch")),
    )
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))

    with pytest.raises(ValueError, match="page count mismatch"):
        translate_input(source, output, client=client)

    assert not output.exists()
    assert not output.with_suffix(".audit.json").exists()


def test_translate_input_retries_a_translation_that_does_not_fit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (200, 200), "white").save(source)
    output = tmp_path / "output.docx"
    region = RegionIR(
        region_id="p0001-r0001",
        kind="text",
        box=BoundingBox(x=0, y=0, width=80, height=30),
        source_text="Bezeichnung",
    )
    blocker = RegionIR(
        region_id="p0001-r0002",
        kind="text",
        box=BoundingBox(x=100, y=0, width=20, height=30),
        translation_eligible=False,
    )
    extraction = ExtractionResponse(
        pages=[
            PageIR(
                page_number=1,
                geometry=PageGeometry(width_points=200, height_points=200),
                regions=[region, blocker],
                reading_order=[region.region_id, blocker.region_id],
            )
        ]
    )
    translation_calls = 0

    def parse(*, text_format: type[BaseModel], **_: object) -> SimpleNamespace:
        nonlocal translation_calls
        if text_format is ExtractionResponse:
            return SimpleNamespace(output_parsed=extraction)
        translation_calls += 1
        text = "A much too long translation" if translation_calls == 1 else "Short"
        return SimpleNamespace(
            output_parsed=TranslationResponse(
                translations=[TranslationItem(region_id=region.region_id, text=text)]
            )
        )

    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))

    translate_input(source, output, client=client)

    assert output.is_file()
    assert translation_calls == 2
