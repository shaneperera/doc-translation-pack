"""Terra extraction response and conversion into the document IR."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from doc_translation.adapters.terra import call_terra
from doc_translation.domain.document import DocumentIR, PageIR


class ExtractionResponse(BaseModel):
    """Structured page and region data returned by Terra."""

    model_config = ConfigDict(extra="forbid")

    pages: list[PageIR]
    language: str | None = None


def extract_document(
    prompt: str,
    source_sha256: str,
    client: Any = None,
) -> DocumentIR:
    """Call Terra and attach the trusted normalized-input hash to its page data."""

    result = call_terra(prompt, ExtractionResponse, client)
    return DocumentIR(
        source_sha256=source_sha256,
        pages=result.parsed.pages,
        language=result.parsed.language,
    )
