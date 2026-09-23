"""Content-fidelity checks for translated regions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from doc_translation.domain.region import RegionIR


class Diagnostic(BaseModel):
    """One actionable content-fidelity problem."""

    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "missing_region",
        "unexpected_region",
        "immutable_token_drift",
        "non_translatable_text_changed",
        "critical_token_missing",
        "critical_token_extra",
        "relationship_drift",
        "unreadable_marker_missing",
        "watermark_omission_unlogged",
    ]
    severity: Literal["error", "warning"]
    page_number: int | None = None
    region_id: str | None = None
    expected: str | None = None
    observed: str | None = None


class ValidationResult(BaseModel):
    """All diagnostics produced by one content-fidelity validation pass."""

    model_config = ConfigDict(extra="forbid")

    diagnostics: list[Diagnostic]
    source_language: str | None = None

    @property
    def passed(self) -> bool:
        return len(self.diagnostics) == 0


def _page_number(region_id: str) -> int | None:
    try:
        return int(region_id.split("-", 1)[0][1:])
    except (IndexError, ValueError):
        return None


def validate_content(
    regions: list[RegionIR],
    translated_text: dict[str, str],
    source_language: str | None = None,
) -> ValidationResult:
    """Compare delivered region text with source IDs, tokens, and preserved spans."""

    source_by_id = {region.region_id: region for region in regions}
    expected_ids = set(source_by_id)
    actual_ids = set(translated_text)
    diagnostics: list[Diagnostic] = []

    for region_id in sorted(expected_ids - actual_ids):
        diagnostics.append(
            Diagnostic(
                code="missing_region",
                severity="error",
                page_number=_page_number(region_id),
                region_id=region_id,
                expected="translated text",
                observed="missing",
            )
        )
    for region_id in sorted(actual_ids - expected_ids):
        diagnostics.append(
            Diagnostic(
                code="unexpected_region",
                severity="error",
                page_number=_page_number(region_id),
                region_id=region_id,
                expected="known source region",
                observed="unexpected translation",
            )
        )

    # IDs present in both sets. Only these can be checked for token drift and unchanged text
    for region_id in sorted(expected_ids & actual_ids):
        region = source_by_id[region_id]
        observed = translated_text[region_id]
        for token in region.immutable_tokens:
            if token not in observed:
                diagnostics.append(
                    Diagnostic(
                        code="immutable_token_drift",
                        severity="error",
                        page_number=_page_number(region_id),
                        region_id=region_id,
                        expected=token,
                        observed=observed,
                    )
                )
        # Applies only to text that must not be translated. Entire source text must remain equal 
        if (
            not region.translation_eligible
            and region.source_text is not None
            and observed != region.source_text
        ):
            diagnostics.append(
                Diagnostic(
                    code="non_translatable_text_changed",
                    severity="error",
                    page_number=_page_number(region_id),
                    region_id=region_id,
                    expected=region.source_text,
                    observed=observed,
                )
            )

    return ValidationResult(diagnostics=diagnostics, source_language=source_language)
