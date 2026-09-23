"""Small OpenAI Responses API call for GPT-5.6 Terra."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
TERRA_MODEL = "gpt-5.6-terra"


@dataclass(frozen=True)
class TerraResult(Generic[T]):
    """Parsed model output plus the minimum request metadata for this call."""

    parsed: T
    model: str
    input_sha256: str
    latency_seconds: float


def call_terra(
    prompt: str,
    response_model: type[T],
    client: Any = None,
) -> TerraResult[T]:
    """Call Terra with a Pydantic response model and reject empty parsed output."""

    if client is None:
        client = OpenAI()

    input_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    started = time.perf_counter()
    response = client.responses.parse(
        model=TERRA_MODEL,
        input=[{"role": "user", "content": prompt}],
        reasoning={"effort": "medium"},
        store=False,
        text_format=response_model,
    )
    latency_seconds = time.perf_counter() - started

    if response.output_parsed is None:
        raise ValueError("Terra returned no parsed result")

    return TerraResult(
        parsed=response.output_parsed,
        model=TERRA_MODEL,
        input_sha256=input_sha256,
        latency_seconds=latency_seconds,
    )
