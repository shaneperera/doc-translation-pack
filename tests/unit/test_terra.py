from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from doc_translation.adapters.terra import TERRA_MODEL, call_terra


class ExampleResult(BaseModel):
    text: str


def test_call_terra_uses_fixed_model_and_returns_parsed_result() -> None:
    client = Mock()
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=ExampleResult(text="ok")
    )

    result = call_terra("translate this", ExampleResult, client)

    assert result.parsed == ExampleResult(text="ok")
    assert result.model == TERRA_MODEL
    assert result.input_sha256
    assert result.latency_seconds >= 0
    client.responses.parse.assert_called_once_with(
        model=TERRA_MODEL,
        input=[{"role": "user", "content": "translate this"}],
        reasoning={"effort": "medium"},
        store=False,
        text_format=ExampleResult,
    )


def test_call_terra_fails_when_no_structured_result_is_returned() -> None:
    client = Mock()
    client.responses.parse.return_value = SimpleNamespace(output_parsed=None)

    with pytest.raises(ValueError, match="no parsed result"):
        call_terra("translate this", ExampleResult, client)
