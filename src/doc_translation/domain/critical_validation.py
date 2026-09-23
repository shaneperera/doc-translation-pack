"""Critical-token, relationship, and special-region fidelity checks."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from doc_translation.domain.content_validation import Diagnostic
from doc_translation.domain.region import RegionIR

UNREADABLE_MARKER = "[Unreadable source text]"


class CriticalToken(BaseModel):
    """A structured value that must match between independent inventories."""

    model_config = ConfigDict(extra="forbid")

    region_id: str
    value: str = Field(min_length=1)
    kind: Literal["number", "date", "identifier", "unit", "operator"]
    unit: str | None = None
    operator: str | None = None
    related_region_id: str | None = None


def _token_key(token: CriticalToken) -> tuple[str, str, str, str | None, str | None, str | None]:
    return (
        token.region_id,
        token.value,
        token.kind,
        token.unit,
        token.operator,
        token.related_region_id,
    )


def compare_critical_tokens(
    primary: list[CriticalToken],
    independent: list[CriticalToken],
) -> list[Diagnostic]:
    """Report critical tuples present in only one inventory."""

    primary_by_key = {_token_key(token): token for token in primary}
    independent_by_key = {_token_key(token): token for token in independent}
    diagnostics: list[Diagnostic] = []

    for key in sorted(set(independent_by_key) - set(primary_by_key)):
        token = independent_by_key[key]
        diagnostics.append(
            Diagnostic(
                code="critical_token_missing",
                severity="error",
                region_id=token.region_id,
                expected=str(key),
                observed="missing from primary inventory",
            )
        )
    for key in sorted(set(primary_by_key) - set(independent_by_key)):
        token = primary_by_key[key]
        diagnostics.append(
            Diagnostic(
                code="critical_token_extra",
                severity="error",
                region_id=token.region_id,
                expected="independent inventory tuple",
                observed=str(key),
            )
        )
    return diagnostics


def compare_relationships(
    source_regions: list[RegionIR],
    translated_regions: list[RegionIR],
) -> list[Diagnostic]:
    """Report a changed parent relationship for a shared region ID."""

    source_by_id = {region.region_id: region for region in source_regions}
    translated_by_id = {region.region_id: region for region in translated_regions}
    diagnostics: list[Diagnostic] = []
    for region_id in sorted(set(source_by_id) & set(translated_by_id)):
        expected = source_by_id[region_id].parent_region_id
        observed = translated_by_id[region_id].parent_region_id
        if expected != observed:
            diagnostics.append(
                Diagnostic(
                    code="relationship_drift",
                    severity="error",
                    region_id=region_id,
                    expected=expected,
                    observed=observed,
                )
            )
    return diagnostics


def validate_special_regions(
    regions: list[RegionIR],
    translated_text: dict[str, str],
    omitted_watermark_ids: set[str],
) -> list[Diagnostic]:
    """Require unreadable markers and logged omissions for confirmed watermarks."""

    diagnostics: list[Diagnostic] = []
    for region in regions:
        if region.unreadable and translated_text.get(region.region_id) != UNREADABLE_MARKER:
            diagnostics.append(
                Diagnostic(
                    code="unreadable_marker_missing",
                    severity="error",
                    region_id=region.region_id,
                    expected=UNREADABLE_MARKER,
                    observed=translated_text.get(region.region_id),
                )
            )
        if (
            region.kind == "watermark"
            and region.region_id not in translated_text
            and region.region_id not in omitted_watermark_ids
        ):
            diagnostics.append(
                Diagnostic(
                    code="watermark_omission_unlogged",
                    severity="error",
                    region_id=region.region_id,
                    expected="logged confirmed omission",
                    observed="omission not logged",
                )
            )
    return diagnostics
