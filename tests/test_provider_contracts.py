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
from batchling.providers.vertex import VertexProvider
from batchling.providers.xai import XaiProvider


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
        VertexProvider(),
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
        VertexProvider(),
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
    host = (
        "us-central1-aiplatform.googleapis.com" if provider.name == "vertex" else "api.openai.com"
    )
    context = provider.build_resume_context(host=host, headers={"Authorization": "Bearer token"})
    assert context.base_url.startswith("https://")
    assert context.api_headers["x-batchling-internal"] == "1"


@pytest.mark.asyncio
async def test_parse_poll_response_default_fields_for_openai_provider() -> None:
    """
    Ensure default poll parser normalizes IDs and computes progress from counts.
    """
    provider = OpenAIProvider()
    snapshot = await provider.parse_poll_response(
        payload={
            "status": "completed",
            "output_file_id": "out-123",
            "error_file_id": "err-123",
            "request_counts": {"completed": 3},
        },
        requests_count=6,
    )
    assert snapshot.status == "completed"
    assert snapshot.output_file_id == "out-123"
    assert snapshot.error_file_id == "err-123"
    assert snapshot.progress_completed == 3
    assert snapshot.progress_percent == 50.0


@pytest.mark.asyncio
async def test_parse_poll_response_progress_defaults_to_zero_for_invalid_numbers() -> None:
    """
    Ensure invalid progress payload values fallback to zero.
    """
    provider = OpenAIProvider()
    snapshot = await provider.parse_poll_response(
        payload={"request_counts": {"completed": "not-a-number"}},
        requests_count=6,
    )
    assert snapshot.progress_completed == 0
    assert snapshot.progress_percent == 0.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "payload", "requests_count", "expected_completed", "expected_percent"),
    [
        (
            AnthropicProvider(),
            {"request_counts": {"succeeded": 4}},
            10,
            4,
            40.0,
        ),
        (
            GeminiProvider(),
            {"batchStats": {"successfulRequestCount": "5"}},
            8,
            5,
            62.5,
        ),
        (
            VertexProvider(),
            {"completionStats": {"successfulCount": 3, "failedCount": "2"}},
            8,
            5,
            62.5,
        ),
        (
            MistralProvider(),
            {"completed_requests": 2},
            4,
            2,
            50.0,
        ),
        (
            XaiProvider(),
            {"state": {"success": 7}},
            7,
            7,
            100.0,
        ),
        (
            TogetherProvider(),
            {"progress": 33.3},
            7,
            2,
            (2 / 7) * 100.0,
        ),
        (
            TogetherProvider(),
            {"progress": 150},
            5,
            5,
            100.0,
        ),
    ],
)
async def test_parse_poll_response_provider_progress_mappings(
    provider: t.Any,
    payload: dict[str, t.Any],
    requests_count: int,
    expected_completed: int,
    expected_percent: float,
) -> None:
    """
    Ensure provider poll progress extraction follows provider-specific mapping rules.
    """
    snapshot = await provider.parse_poll_response(
        payload=payload,
        requests_count=requests_count,
    )
    assert snapshot.progress_completed == expected_completed
    assert snapshot.progress_percent == pytest.approx(expected_percent)


@pytest.mark.asyncio
async def test_parse_poll_response_vertex_sets_result_locator() -> None:
    """
    Ensure Vertex poll payload exposes its GCS output directory as result locator.
    """
    provider = VertexProvider()
    snapshot = await provider.parse_poll_response(
        payload={
            "state": "JOB_STATE_SUCCEEDED",
            "completionStats": {"successfulCount": 1, "failedCount": 0},
            "outputInfo": {"gcsOutputDirectory": "gs://bucket/output/prefix"},
        },
        requests_count=1,
    )
    assert snapshot.status == "JOB_STATE_SUCCEEDED"
    assert snapshot.output_file_id == ""
    assert snapshot.error_file_id == ""
    assert snapshot.result_locator == "gs://bucket/output/prefix"


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

    vertex_provider = VertexProvider()
    vertex_results = vertex_provider.decode_results_content(
        batch_id="batch-vertex",
        content='{"key":"req-3","response":{"ok":true}}\n',
    )
    assert "req-3" in vertex_results
    assert isinstance(vertex_results["req-3"], httpx.Response)


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
    snapshot = await provider.parse_poll_response(payload=payload, requests_count=3)
    assert snapshot.status == expected_status
    assert snapshot.output_file_id == ""
    assert snapshot.error_file_id == ""
    assert snapshot.progress_completed == 0
    assert snapshot.progress_percent == 0.0


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
