"""Translation response validation and one targeted retry."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from doc_translation.adapters.terra import call_terra
from doc_translation.domain.region import RegionIR


class TranslationResponse(BaseModel):
    """The exact region-to-text object expected from a translation request."""

    model_config = ConfigDict(extra="forbid")

    translations: dict[str, str]


class TranslationValidationError(ValueError):
    """A translation response cannot be applied to the requested regions."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("; ".join(issues))


def validate_translation(
    response: TranslationResponse,
    regions: list[RegionIR],
) -> dict[str, str]:
    """Require every eligible region exactly once and preserve immutable tokens."""

    eligible_regions = {
        region.region_id: region for region in regions if region.translation_eligible
    }
    expected_ids = set(eligible_regions)
    actual_ids = set(response.translations)
    issues: list[str] = []

    for region_id in sorted(expected_ids - actual_ids):
        issues.append(f"missing translation: {region_id}")
    for region_id in sorted(actual_ids - expected_ids):
        issues.append(f"unexpected translation: {region_id}")
    for region_id in sorted(expected_ids & actual_ids):
        text = response.translations[region_id]
        if not text.strip():
            issues.append(f"empty translation: {region_id}")
        for token in eligible_regions[region_id].immutable_tokens:
            if token not in text:
                issues.append(f"immutable token drift: {region_id}:{token}")

    if issues:
        raise TranslationValidationError(issues)
    return response.translations


def translate_regions(
    prompt: str,
    regions: list[RegionIR],
    client: Any = None,
) -> dict[str, str]:
    """Call Terra and retry once with the validation issues if its mapping is unsafe."""

    retry_prompt = prompt
    for attempt in range(2):
        result = call_terra(retry_prompt, TranslationResponse, client)
        try:
            return validate_translation(result.parsed, regions)
        except TranslationValidationError as error:
            if attempt == 1:
                raise
            retry_prompt = f"{prompt}\nCorrect only these issues:\n" + "\n".join(error.issues)

    raise AssertionError("translation retry loop did not return or raise")
