"""Tests for provider-side polling/results/resume contracts."""

import typing as t

import httpx
import pytest

from batchling.providers.anthropic import AnthropicProvider
from batchling.providers.doubleword import DoublewordProvider
from batchling.providers.gemini import GeminiProvider
from batchling.providers.groq import GroqProvider
from batchling.providers.mistral import MistralProvider
from batchling.providers.openai import OpenAIProvider
from batchling.providers.together import TogetherProvider


@pytest.mark.parametrize(
    "provider",
    [
        OpenAIProvider(),
        MistralProvider(),
        GeminiProvider(),
        AnthropicProvider(),
        GroqProvider(),
        TogetherProvider(),
        DoublewordProvider(),
    ],
)
def test_build_poll_request_spec_returns_get(provider: t.Any) -> None:
    """
    Ensure all providers expose poll request specs.

    Parameters
    ----------
    provider : typing.Any
        Provider instance under test.
    """
    spec = provider.build_poll_request_spec(
        base_url="https://api.example.com",
        api_headers={"Authorization": "Bearer token"},
        batch_id="batch-123",
    )
    assert spec.method == "GET"
    assert spec.path
    assert isinstance(spec.headers, dict)


@pytest.mark.parametrize(
    "provider",
    [
        OpenAIProvider(),
        MistralProvider(),
        GeminiProvider(),
        AnthropicProvider(),
        GroqProvider(),
        TogetherProvider(),
        DoublewordProvider(),
    ],
)
def test_build_resume_context_adds_internal_header(provider: t.Any) -> None:
    """
    Ensure resumed context includes internal bypass headers.

    Parameters
    ----------
    provider : typing.Any
        Provider instance under test.
    """
    context = provider.build_resume_context(
        host="api.openai.com",
        headers={"Authorization": "Bearer token"},
    )
    assert context.base_url.startswith("https://")
    assert context.api_headers["x-batchling-internal"] == "1"


@pytest.mark.asyncio
async def test_parse_poll_response_default_fields_for_openai_provider() -> None:
    """
    Ensure default poll parser normalizes output and error IDs.
    """
    provider = OpenAIProvider()
    snapshot = await provider.parse_poll_response(
        payload={
            "status": "completed",
            "output_file_id": "out-123",
            "error_file_id": "err-123",
        }
    )
    assert snapshot.status == "completed"
    assert snapshot.output_file_id == "out-123"
    assert snapshot.error_file_id == "err-123"


def test_decode_results_content_maps_custom_ids() -> None:
    """
    Ensure provider decoders map custom IDs to ``httpx.Response`` values.
    """
    openai_provider = OpenAIProvider()
    openai_results = openai_provider.decode_results_content(
        batch_id="batch-openai",
        content='{"custom_id":"req-1","response":{"status_code":200,"body":{"ok":true}}}\n',
    )
    assert "req-1" in openai_results
    assert isinstance(openai_results["req-1"], httpx.Response)

    gemini_provider = GeminiProvider()
    gemini_results = gemini_provider.decode_results_content(
        batch_id="batch-gemini",
        content='{"key":"req-2","response":{"status_code":200,"body":{"ok":true}}}\n',
    )
    assert "req-2" in gemini_results
    assert isinstance(gemini_results["req-2"], httpx.Response)
