from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from doc_translation.adapters.translation import (
    TranslationItem,
    TranslationResponse,
    TranslationValidationError,
    translate_regions,
    validate_translation,
)
from doc_translation.domain.region import BoundingBox, RegionIR

FIXTURE = Path(__file__).parents[1] / "fixtures" / "translation_response.json"


def _regions() -> list[RegionIR]:
    return [
        RegionIR(
            region_id="p0001-r0001",
            kind="text",
            box=BoundingBox(x=0, y=0, width=10, height=10),
            immutable_tokens=["1234"],
        )
    ]


def test_recorded_translation_fixture_is_valid() -> None:
    response = TranslationResponse.model_validate_json(FIXTURE.read_text())

    assert validate_translation(response, _regions()) == {
        "p0001-r0001": "Patient number 1234"
    }


def test_response_schema_uses_a_list_for_structured_output() -> None:
    schema = TranslationResponse.model_json_schema()

    assert schema["properties"]["translations"]["type"] == "array"


def test_validation_accepts_unicode_width_variant_of_immutable_token() -> None:
    region = _regions()[0].model_copy(update={"immutable_tokens": ["２"]})

    assert validate_translation(
        TranslationResponse(
            translations=[TranslationItem(region_id=region.region_id, text="2")]
        ),
        [region],
    ) == {region.region_id: "2"}


def test_validation_rejects_missing_extra_empty_and_drifted_values() -> None:
    response = TranslationResponse(
        translations=[
            TranslationItem(region_id="p0001-r0002", text="Other"),
            TranslationItem(region_id="p0001-r0001", text=""),
        ]
    )

    with pytest.raises(TranslationValidationError) as error:
        validate_translation(response, _regions())

    assert "unexpected translation: p0001-r0002" in error.value.issues
    assert "empty translation: p0001-r0001" in error.value.issues
    assert "immutable token drift: p0001-r0001:1234" in error.value.issues


def test_translate_regions_retries_once_with_issues() -> None:
    client = Mock()
    client.responses.parse.side_effect = [
        SimpleNamespace(output_parsed=TranslationResponse(translations=[])),
        SimpleNamespace(
            output_parsed=TranslationResponse(
                translations=[
                    TranslationItem(region_id="p0001-r0001", text="Patient number 1234")
                ]
            )
        ),
    ]

    result = translate_regions("Translate this", _regions(), client)

    assert result["p0001-r0001"] == "Patient number 1234"
    assert client.responses.parse.call_count == 2
    retry_prompt = client.responses.parse.call_args_list[1].kwargs["input"][0]["content"]
    assert "missing translation: p0001-r0001" in retry_prompt


def test_translate_regions_fails_after_one_retry() -> None:
    client = Mock()
    client.responses.parse.side_effect = [
        SimpleNamespace(output_parsed=TranslationResponse(translations=[])),
        SimpleNamespace(output_parsed=TranslationResponse(translations=[])),
    ]

    with pytest.raises(TranslationValidationError):
        translate_regions("Translate this", _regions(), client)

    assert client.responses.parse.call_count == 2
