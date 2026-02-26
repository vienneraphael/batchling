"""Tests for provider-side polling/results/resume contracts."""

import typing as t

import httpx
import pytest

from batchling.providers.anthropic import AnthropicProvider
from batchling.providers.base import BaseProvider
from batchling.providers.doubleword import DoublewordProvider
from batchling.providers.gemini import GeminiProvider
from batchling.providers.groq import GroqProvider
from batchling.providers.mistral import MistralProvider
from batchling.providers.openai import OpenAIProvider
from batchling.providers.together import TogetherProvider
from batchling.providers.xai import XaiProvider


def test_legacy_hostnames_attribute_raises() -> None:
    """
    Ensure providers fail fast when defining removed ``hostnames``.
    """
    with pytest.raises(
        expected_exception=TypeError,
        match="`hostnames` has been removed",
    ):

        class LegacyHostnamesProvider(BaseProvider):
            name = "legacy"
            hostnames = ("api.legacy.example",)


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
        XaiProvider(),
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
        XaiProvider(),
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"state": {"num_pending": 2, "num_completed": 0}}, "pending"),
        ({"state": {"num_pending": 1, "num_completed": 1}}, "running"),
        ({"state": {"num_pending": 0, "num_completed": 2}}, "ended"),
        ({}, "ended"),
    ],
)
async def test_parse_poll_response_xai_state_mapping(
    payload: dict[str, t.Any], expected_status: str
) -> None:
    """
    Ensure Xai poll payload state counts map to normalized poll statuses.

    Parameters
    ----------
    payload : dict[str, typing.Any]
        Xai poll response payload.
    expected_status : str
        Expected normalized poll status.
    """
    provider = XaiProvider()
    snapshot = await provider.parse_poll_response(payload=payload)
    assert snapshot.status == expected_status
    assert snapshot.output_file_id == ""
    assert snapshot.error_file_id == ""


def test_decode_results_content_xai_maps_response_and_error_rows() -> None:
    """
    Ensure Xai result payload maps request IDs to ``httpx.Response`` objects.
    """
    provider = XaiProvider()
    xai_results = provider.decode_results_content(
        batch_id="batch-xai",
        content=(
            '{"results":['
            '{"batch_request_id":"req-ok","batch_result":{"response":{"headers":{"x-test":"1"},"id":"ok"}}},'
            '{"batch_result":{"response":{"id":"missing-id"}}},'
            '{"batch_request_id":"req-error","batch_result":{"error":{"message":"boom"}}}'
            "]}"
        ),
    )

    assert set(xai_results.keys()) == {"req-ok", "req-error"}
    assert xai_results["req-ok"].status_code == 200
    assert xai_results["req-ok"].headers["x-test"] == "1"
    assert xai_results["req-ok"].json()["id"] == "ok"

    assert xai_results["req-error"].status_code == 500
    assert xai_results["req-error"].json()["message"] == "boom"
