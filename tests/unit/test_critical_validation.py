from __future__ import annotations

from doc_translation.domain.critical_validation import (
    UNREADABLE_MARKER,
    CriticalToken,
    compare_critical_tokens,
    validate_special_regions,
)
from doc_translation.domain.region import BoundingBox, RegionIR


def _token(value: str, *, related_region_id: str | None = None) -> CriticalToken:
    return CriticalToken(
        region_id="p0001-r0001",
        value=value,
        kind="number",
        unit="mg",
        related_region_id=related_region_id,
    )


def _region(
    region_id: str = "p0001-r0001",
    *,
    parent_region_id: str | None = None,
    kind: str = "text",
    unreadable: bool = False,
) -> RegionIR:
    return RegionIR(
        region_id=region_id,
        kind=kind,  # type: ignore[arg-type]
        box=BoundingBox(x=0, y=0, width=10, height=10),
        parent_region_id=parent_region_id,
        unreadable=unreadable,
    )


def test_critical_inventory_difference_reports_missing_and_extra() -> None:
    diagnostics = compare_critical_tokens([_token("50")], [_token("5")])

    assert [diagnostic.code for diagnostic in diagnostics] == [
        "critical_token_missing",
        "critical_token_extra",
    ]


def test_special_regions_require_marker_and_watermark_log() -> None:
    regions = [
        _region(unreadable=True),
        _region("p0001-r0002", kind="watermark"),
    ]

    diagnostics = validate_special_regions(regions, {}, set())

    assert [diagnostic.code for diagnostic in diagnostics] == [
        "unreadable_marker_missing",
        "watermark_omission_unlogged",
    ]

    assert validate_special_regions(
        regions,
        {"p0001-r0001": UNREADABLE_MARKER},
        {"p0001-r0002"},
    ) == []
