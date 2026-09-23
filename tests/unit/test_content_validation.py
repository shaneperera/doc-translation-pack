from __future__ import annotations

from doc_translation.domain.content_validation import validate_content
from doc_translation.domain.region import BoundingBox, RegionIR


def _region(
    region_id: str = "p0001-r0001",
    *,
    source_text: str | None = "Patient number 1234",
    translation_eligible: bool = True,
) -> RegionIR:
    return RegionIR(
        region_id=region_id,
        kind="text",
        box=BoundingBox(x=0, y=0, width=10, height=10),
        source_text=source_text,
        translation_eligible=translation_eligible,
        immutable_tokens=["1234"],
    )


def test_valid_content_passes_and_preserves_source_language_override() -> None:
    result = validate_content(
        [_region()],
        {"p0001-r0001": "Patient number 1234"},
        source_language="de",
    )

    assert result.passed
    assert result.source_language == "de"


def test_missing_and_unexpected_regions_are_diagnostics() -> None:
    result = validate_content(
        [_region()],
        {"p0001-r0002": "Other"},
    )

    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "missing_region",
        "unexpected_region",
    ]
    assert result.diagnostics[0].page_number == 1


def test_token_drift_is_a_failed_diagnostic() -> None:
    result = validate_content(
        [_region()],
        {"p0001-r0001": "Patient number 4321"},
    )

    assert not result.passed
    assert result.diagnostics[0].code == "immutable_token_drift"
    assert result.diagnostics[0].expected == "1234"


def test_full_width_token_variant_is_preserved_semantically() -> None:
    region = _region()
    region.immutable_tokens = ["２"]

    result = validate_content([region], {region.region_id: "Value 2"})

    assert result.passed


def test_non_translatable_unicode_text_must_remain_exact() -> None:
    region = _region(
        source_text="Ångström ✓",
        translation_eligible=False,
    )
    region.immutable_tokens.clear()

    result = validate_content(
        [region],
        {"p0001-r0001": "Angstrom ✓"},
    )

    assert not result.passed
    assert result.diagnostics[0].code == "non_translatable_text_changed"
