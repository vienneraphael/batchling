"""
Tests for the Batcher class in batchling.core.
"""

import asyncio
import contextlib
import time
import typing as t

import httpx
import pytest

from batchling.cache import CacheEntry
from batchling.core import Batcher, _PendingRequest
from batchling.exceptions import DeferredExit
from batchling.providers.anthropic import AnthropicProvider
from batchling.providers.gemini import GeminiProvider
from batchling.providers.mistral import MistralProvider
from batchling.providers.openai import OpenAIProvider
from tests.mocks.batching import make_openai_batch_transport

QueueKey = tuple[str, str, str]


class HomogeneousOpenAIProvider(OpenAIProvider):
    """OpenAI-like provider with custom provider name for queue-key tests."""

    name = "homogeneous-openai"


@pytest.fixture
def provider() -> OpenAIProvider:
    """
    Create an OpenAI provider instance.
    """
    return OpenAIProvider()


@pytest.fixture
def mock_openai_api_transport() -> httpx.MockTransport:
    """
    Create a mock OpenAI batch transport.

    Returns
    -------
    httpx.MockTransport
        Mock transport for OpenAI batch endpoints.
    """
    return make_openai_batch_transport()


@pytest.fixture
def batcher(mock_openai_api_transport: httpx.MockTransport) -> Batcher:
    """
    Create a Batcher instance for testing.

    Returns
    -------
    Batcher
        Configured batcher instance.
    """
    batcher = Batcher(batch_size=3, batch_window_seconds=0.5, cache=False)
    batcher._client_factory = lambda: httpx.AsyncClient(transport=mock_openai_api_transport)
    batcher._poll_interval_seconds = 0.01
    return batcher


@pytest.fixture
def fast_batcher(mock_openai_api_transport: httpx.MockTransport) -> Batcher:
    """
    Create a Batcher with a very short window for fast tests.

    Returns
    -------
    Batcher
        Configured batcher instance.
    """
    batcher = Batcher(batch_size=2, batch_window_seconds=0.1, cache=False)
    batcher._client_factory = lambda: httpx.AsyncClient(transport=mock_openai_api_transport)
    batcher._poll_interval_seconds = 0.01
    return batcher


def _pending_count(batcher: Batcher) -> int:
    """
    Return total pending request count across providers.

    Parameters
    ----------
    batcher : Batcher
        Target batcher.

    Returns
    -------
    int
        Total pending request count.
    """
    return sum(len(queue) for queue in batcher._pending_by_provider.values())


def _pending_count_for_provider(batcher: Batcher, provider_name: str) -> int:
    """
    Return pending request count for a provider.

    Parameters
    ----------
    batcher : Batcher
        Target batcher.
    provider_name : str
        Provider key.

    Returns
    -------
    int
        Pending request count for the provider.
    """
    return sum(
        len(queue)
        for queue_key, queue in batcher._pending_by_provider.items()
        if queue_key[0] == provider_name
    )


def _queue_key(
    *,
    provider_name: str,
    endpoint: str = "/v1/chat/completions",
    model_name: str = "model-a",
) -> QueueKey:
    """
    Build queue key used by Batcher internals.

    Parameters
    ----------
    provider_name : str
        Provider name component.
    endpoint : str, optional
        Endpoint partition component.
    model_name : str, optional
        Model partition component.

    Returns
    -------
    QueueKey
        Queue key tuple.
    """
    return provider_name, endpoint, model_name


@pytest.mark.asyncio
async def test_batcher_initialization():
    """Test that Batcher initializes with correct parameters."""
    batcher = Batcher(
        batch_size=10,
        batch_window_seconds=2.0,
        batch_poll_interval_seconds=5.0,
        cache=False,
    )

    assert batcher._batch_size == 10
    assert batcher._batch_window_seconds == 2.0
    assert batcher._poll_interval_seconds == 5.0
    assert _pending_count(batcher=batcher) == 0
    assert len(batcher._active_batches) == 0
    assert batcher._window_tasks == {}


@pytest.mark.asyncio
async def test_submit_single_request(batcher: Batcher, provider: OpenAIProvider):
    """Test submitting a single request."""
    result = await batcher.submit(
        client_type="httpx",
        method="GET",
        url="api.openai.com",
        endpoint="/v1/chat/completions",
        provider=provider,
        body=b'{"model":"model-a","messages":[]}',
        headers={"Authorization": "Bearer token"},
    )

    assert isinstance(result, httpx.Response)
    assert result.status_code == 200
    assert _pending_count(batcher=batcher) == 0
    assert len(batcher._active_batches) == 1


@pytest.mark.asyncio
async def test_submit_multiple_requests_queued(batcher: Batcher, provider: OpenAIProvider):
    """Test that multiple requests are queued before batch size is reached."""
    # Submit 2 requests (less than batch_size=3)
    task1 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )
    task2 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )

    # Give a small delay to ensure requests are queued
    await asyncio.sleep(delay=0.05)

    # Should have 2 pending requests
    assert _pending_count_for_provider(batcher=batcher, provider_name="openai") == 2
    assert _queue_key(provider_name="openai") in batcher._window_tasks

    # Wait for both tasks to complete
    await task1
    await task2


@pytest.mark.asyncio
async def test_batch_size_threshold_triggers_submission(batcher: Batcher, provider: OpenAIProvider):
    """Test that batch submission is triggered when batch_size is reached."""
    results = await asyncio.gather(
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
    )

    # All requests should complete
    assert all(isinstance(r, httpx.Response) and r.status_code == 200 for r in results)

    # Pending queue should be empty (batch was submitted)
    assert _pending_count(batcher=batcher) == 0

    # Should have one active batch
    assert len(batcher._active_batches) == 1

    # Window task should be cancelled/None
    assert _queue_key(provider_name="openai") not in batcher._window_tasks


@pytest.mark.asyncio
async def test_window_time_triggers_submission(fast_batcher: Batcher, provider: OpenAIProvider):
    """Test that batch submission is triggered after window time elapses."""
    # Submit 1 request (less than batch_size=2)
    task = asyncio.create_task(
        fast_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )

    # Wait for window time to elapse (0.1 seconds)
    await asyncio.sleep(delay=0.15)

    # Request should complete
    result = await task
    assert isinstance(result, httpx.Response)
    assert result.status_code == 200

    # Pending queue should be empty
    assert _pending_count(batcher=fast_batcher) == 0

    # Should have one active batch
    assert len(fast_batcher._active_batches) == 1


@pytest.mark.asyncio
async def test_window_timer_cancelled_on_size_threshold(batcher: Batcher, provider: OpenAIProvider):
    """Test that window timer is cancelled when batch size threshold is reached."""
    # Submit 2 requests to start the timer
    task1 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )
    task2 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )

    await asyncio.sleep(delay=0.05)

    # Timer should be running
    assert _queue_key(provider_name="openai") in batcher._window_tasks
    assert not batcher._window_tasks[_queue_key(provider_name="openai")].done()

    # Submit third request to trigger size threshold
    task3 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )

    await asyncio.gather(task1, task2, task3)

    # Timer should be cancelled/None
    assert _queue_key(provider_name="openai") not in batcher._window_tasks


@pytest.mark.asyncio
async def test_multiple_batches_submitted(fast_batcher: Batcher, provider: OpenAIProvider):
    """Test that multiple batches can be submitted sequentially."""
    # Submit first batch (size threshold)
    await asyncio.gather(
        fast_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
        fast_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
    )

    # Submit second batch (size threshold)
    await asyncio.gather(
        fast_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
        fast_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
    )

    # Should have 2 active batches
    assert len(fast_batcher._active_batches) == 2
    assert _pending_count(batcher=fast_batcher) == 0


@pytest.mark.asyncio
async def test_concurrent_requests(batcher: Batcher, provider: OpenAIProvider):
    """Test handling of concurrent requests."""
    # Submit 5 requests concurrently (will create 2 batches)
    tasks = [
        asyncio.create_task(
            batcher.submit(
                client_type="httpx",
                method="GET",
                url="api.openai.com",
                endpoint="/v1/chat/completions",
                provider=provider,
                body=b'{"model":"model-a","messages":[]}',
                headers={"Authorization": "Bearer token"},
            )
        )
        for i in range(5)
    ]

    results = await asyncio.gather(*tasks)

    # All should complete
    assert all(isinstance(r, httpx.Response) and r.status_code == 200 for r in results)

    # Should have 2 batches (3 + 2)
    assert len(batcher._active_batches) == 2
    assert _pending_count(batcher=batcher) == 0


@pytest.mark.asyncio
async def test_submit_with_kwargs(batcher: Batcher, provider: OpenAIProvider):
    """Test that submit accepts and stores kwargs."""
    result = await batcher.submit(
        client_type="httpx",
        method="POST",
        url="api.openai.com",
        endpoint="/v1/api",
        json=b'{"model":"model-a","messages":[]}',
        headers={"Authorization": "Bearer token"},
        provider=provider,
        body=b'{"model":"model-a","messages":[]}',
    )

    assert isinstance(result, httpx.Response)
    assert result.status_code == 200

    # Check that the batch contains the request with kwargs
    assert len(batcher._active_batches) == 1
    batch = batcher._active_batches[0]
    assert len(batch.requests) == 1

    request = list(batch.requests.values())[0]
    assert request.params["method"] == "POST"
    assert request.params["url"] == "api.openai.com"
    assert request.params["endpoint"] == "/v1/api"
    assert request.params["json"] == b'{"model":"model-a","messages":[]}'
    assert request.params["headers"] == {"Authorization": "Bearer token"}


@pytest.mark.asyncio
async def test_close_submits_remaining_requests(fast_batcher: Batcher, provider: OpenAIProvider):
    """Test that close() submits any remaining pending requests."""
    # Submit 1 request (less than batch_size)
    task = asyncio.create_task(
        fast_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )

    # Don't wait for window, close immediately
    await asyncio.sleep(delay=0.05)

    # Close should submit the pending request
    await fast_batcher.close()

    # Request should complete
    result = await task
    assert isinstance(result, httpx.Response)
    assert result.status_code == 200

    # Pending should be empty
    assert _pending_count(batcher=fast_batcher) == 0


@pytest.mark.asyncio
async def test_close_cancels_window_timer(fast_batcher: Batcher, provider: OpenAIProvider):
    """Test that close() cancels the window timer."""
    # Submit 1 request to start timer
    task = asyncio.create_task(
        fast_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )

    await asyncio.sleep(delay=0.05)

    # Timer should be running
    assert _queue_key(provider_name="openai") in fast_batcher._window_tasks
    assert not fast_batcher._window_tasks[_queue_key(provider_name="openai")].done()

    # Close should cancel timer and submit batch
    await fast_batcher.close()

    # Timer should be cancelled
    assert _queue_key(provider_name="openai") not in fast_batcher._window_tasks

    # Request should complete
    await task


@pytest.mark.asyncio
async def test_batch_submission_error_handling(
    batcher: Batcher, provider: OpenAIProvider, monkeypatch
):
    """Test that errors during batch submission fail all pending futures."""

    async def failing_process_batch(*_args, **_kwargs):
        raise Exception("Batch submission failed")

    monkeypatch.setattr(
        provider,
        "process_batch",
        failing_process_batch,
    )

    # Submit requests
    task1 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )
    task2 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )
    task3 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )

    # All should fail with the error
    with pytest.raises(Exception, match="Batch submission failed"):
        await asyncio.gather(task1, task2, task3, return_exceptions=False)


@pytest.mark.asyncio
async def test_window_timer_error_handling(
    provider: OpenAIProvider, fast_batcher: Batcher, monkeypatch
):
    """Test that errors during window-triggered submission fail futures."""

    async def failing_process_batch(*_args, **_kwargs):
        raise Exception("Timer error during batch submission")

    monkeypatch.setattr(
        provider,
        "process_batch",
        failing_process_batch,
    )

    # Submit a request - the window timer will trigger and call _submit_batch
    task = asyncio.create_task(
        fast_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )

    # Wait for the window timer to trigger (0.1 seconds)
    await asyncio.sleep(delay=0.15)

    with pytest.raises(Exception, match="Timer error during batch submission"):
        await task

    # Verify the task completed (even though it failed)
    assert task.done()


@pytest.mark.asyncio
async def test_empty_batch_not_submitted(batcher: Batcher, provider: OpenAIProvider):
    """Test that submitting an empty batch does nothing."""
    await batcher._submit_requests(
        queue_key=_queue_key(provider_name=provider.name),
        requests=[],
    )

    # Should have no active batches
    assert len(batcher._active_batches) == 0


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_custom_id_uniqueness(batcher: Batcher, provider: OpenAIProvider):
    """Test that each request gets a unique custom_id."""
    # Submit multiple requests
    await asyncio.gather(
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
    )

    # Get all custom_ids from the batch
    batch = batcher._active_batches[0]
    custom_ids = list(batch.requests.keys())

    # All should be unique
    assert len(custom_ids) == len(set(custom_ids))
    assert len(custom_ids) == 3


@pytest.mark.asyncio
async def test_active_batch_tracking(batcher: Batcher, provider: OpenAIProvider):
    """Test that active batches are properly tracked."""
    # Submit a batch
    await asyncio.gather(
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
        batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
    )

    # Check batch properties
    assert len(batcher._active_batches) == 1
    batch = batcher._active_batches[0]

    assert batch.batch_id is not None
    assert isinstance(batch.created_at, float)
    assert batch.created_at > 0
    assert len(batch.requests) == 3


@pytest.mark.asyncio
async def test_multiple_windows_sequential(fast_batcher: Batcher, provider: OpenAIProvider):
    """Test that multiple windows work sequentially."""
    # First window: submit 1 request, wait for window
    task1 = asyncio.create_task(
        fast_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )
    await asyncio.sleep(delay=0.15)
    await task1

    # Second window: submit 1 request, wait for window
    task2 = asyncio.create_task(
        fast_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        )
    )
    await asyncio.sleep(delay=0.15)
    await task2

    # Should have 2 batches
    assert len(fast_batcher._active_batches) == 2


@pytest.mark.asyncio
async def test_large_batch_size(
    mock_openai_api_transport: httpx.MockTransport, provider: OpenAIProvider
):
    """Test with a larger batch size."""
    large_batcher = Batcher(batch_size=10, batch_window_seconds=0.1, cache=False)
    large_batcher._client_factory = lambda: httpx.AsyncClient(transport=mock_openai_api_transport)
    large_batcher._poll_interval_seconds = 0.01

    # Submit 10 requests to trigger size threshold
    tasks = [
        asyncio.create_task(
            large_batcher.submit(
                client_type="httpx",
                method="GET",
                url="api.openai.com",
                endpoint="/v1/chat/completions",
                provider=provider,
                body=b'{"model":"model-a","messages":[]}',
                headers={"Authorization": "Bearer token"},
            )
        )
        for i in range(10)
    ]

    results = await asyncio.gather(*tasks)
    assert all(isinstance(r, httpx.Response) and r.status_code == 200 for r in results)
    assert len(large_batcher._active_batches) == 1
    assert _pending_count(batcher=large_batcher) == 0


@pytest.mark.asyncio
async def test_close_idempotent(batcher: Batcher, provider: OpenAIProvider):
    """Test that close() can be called multiple times safely."""
    await batcher.close()
    await batcher.close()
    await batcher.close()

    # Should not raise any errors
    assert True


@pytest.mark.asyncio
async def test_submit_after_close(batcher: Batcher, provider: OpenAIProvider):
    """Test behavior when submitting after close."""
    await batcher.close()

    # Submitting after close should still work (batcher is not fully closed)
    # The batcher doesn't prevent new submissions after close
    result = await batcher.submit(
        client_type="httpx",
        method="GET",
        url="api.openai.com",
        endpoint="/v1/chat/completions",
        provider=provider,
        body=b'{"model":"model-a","messages":[]}',
        headers={"Authorization": "Bearer token"},
    )
    assert isinstance(result, httpx.Response)
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_dry_run_returns_simulated_response(provider: OpenAIProvider):
    """Test dry-run returns a simulated response without provider I/O."""
    dry_run_batcher = Batcher(
        batch_size=3,
        batch_window_seconds=0.5,
        dry_run=True,
        cache=False,
    )

    result = await dry_run_batcher.submit(
        client_type="httpx",
        method="GET",
        url="api.openai.com",
        endpoint="/v1/chat/completions",
        provider=provider,
        body=b'{"model":"model-a","messages":[]}',
        headers={"Authorization": "Bearer token"},
    )

    result = await dry_run_batcher.submit(
        client_type="httpx",
        method="GET",
        url="api.openai.com",
        endpoint="/v1/chat/completions",
        provider=provider,
        body=b'{"model":"model-a","messages":[]}',
        headers={"Authorization": "Bearer token"},
    )

    assert isinstance(result, httpx.Response)
    assert result.status_code == 200
    assert result.headers.get("x-batchling-dry-run") == "1"
    assert result.json()["dry_run"] is True
    assert result.json()["provider"] == "openai"
    assert result.json()["status"] == "simulated"
    assert _pending_count(batcher=dry_run_batcher) == 0
    assert len(dry_run_batcher._active_batches) == 2

    await dry_run_batcher.close()


@pytest.mark.asyncio
async def test_dry_run_does_not_call_provider_process_batch(provider: OpenAIProvider, monkeypatch):
    """Test dry-run bypasses provider batch submission."""
    dry_run_batcher = Batcher(
        batch_size=1,
        batch_window_seconds=1.0,
        dry_run=True,
        cache=False,
    )

    call_count = 0

    async def failing_process_batch(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        raise AssertionError("process_batch should not be called in dry_run mode")

    monkeypatch.setattr(
        provider,
        "process_batch",
        failing_process_batch,
    )

    result = await dry_run_batcher.submit(
        client_type="httpx",
        method="GET",
        url="api.openai.com",
        endpoint="/v1/chat/completions",
        provider=provider,
        body=b'{"model":"model-a","messages":[]}',
        headers={"Authorization": "Bearer token"},
    )

    assert result.status_code == 200
    assert call_count == 0

    await dry_run_batcher.close()


@pytest.mark.asyncio
async def test_dry_run_still_batches_by_size(provider: OpenAIProvider):
    """Test dry-run keeps size-threshold batching behavior."""
    dry_run_batcher = Batcher(
        batch_size=3,
        batch_window_seconds=1.0,
        dry_run=True,
        cache=False,
    )

    results = await asyncio.gather(
        dry_run_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
        dry_run_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
        dry_run_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
            headers={"Authorization": "Bearer token"},
        ),
    )

    assert all(isinstance(r, httpx.Response) and r.status_code == 200 for r in results)
    assert len(dry_run_batcher._active_batches) == 1
    assert _pending_count(batcher=dry_run_batcher) == 0

    await dry_run_batcher.close()


@pytest.mark.asyncio
async def test_dry_run_close_flushes_pending_requests(provider: OpenAIProvider):
    """Test close() flushes pending requests in dry-run mode."""
    dry_run_batcher = Batcher(
        batch_size=5,
        batch_window_seconds=10.0,
        dry_run=True,
        cache=False,
    )

    task = asyncio.create_task(
        dry_run_batcher.submit(
            client_type="httpx",
            method="GET",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
        )
    )

    await asyncio.sleep(delay=0.05)
    await dry_run_batcher.close()

    result = await task
    assert isinstance(result, httpx.Response)
    assert result.status_code == 200
    assert result.headers.get("x-batchling-dry-run") == "1"
    assert len(dry_run_batcher._active_batches) == 1


@pytest.mark.asyncio
async def test_homogeneous_provider_same_model_uses_same_queue():
    """Test strict batching groups same endpoint/model requests together."""
    provider = HomogeneousOpenAIProvider()
    batcher = Batcher(batch_size=2, batch_window_seconds=10.0, dry_run=True, cache=False)

    results = await asyncio.gather(
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"gpt-4o-mini","messages":[]}',
        ),
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"gpt-4o-mini","messages":[]}',
        ),
    )

    assert len(batcher._active_batches) == 1
    assert all(result.status_code == 200 for result in results)
    assert _pending_count_for_provider(batcher=batcher, provider_name=provider.name) == 0
    await batcher.close()


@pytest.mark.asyncio
async def test_homogeneous_provider_pending_request_stores_queue_key():
    """Test strict batching stores full queue key on pending requests."""
    provider = HomogeneousOpenAIProvider()
    batcher = Batcher(batch_size=3, batch_window_seconds=10.0, dry_run=True, cache=False)

    task = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
        )
    )

    await asyncio.sleep(delay=0.05)

    queue = batcher._pending_by_provider[
        _queue_key(provider_name=provider.name, model_name="model-a")
    ]
    assert queue[0].queue_key == _queue_key(provider_name=provider.name, model_name="model-a")

    await batcher.close()
    await task


@pytest.mark.asyncio
async def test_strict_queue_key_stores_provider_endpoint_model():
    """Test strict queue keys always store provider, endpoint, and model."""
    provider = OpenAIProvider()
    batcher = Batcher(batch_size=3, batch_window_seconds=10.0, dry_run=True, cache=False)

    task = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
        )
    )

    await asyncio.sleep(delay=0.05)

    queue_key = _queue_key(
        provider_name=provider.name,
        endpoint="/v1/chat/completions",
        model_name="model-a",
    )
    queue = batcher._pending_by_provider[queue_key]
    assert queue[0].queue_key == queue_key

    await batcher.close()
    await task


def test_gemini_queue_key_extracts_model_from_endpoint() -> None:
    """
    Ensure queue partitioning for Gemini reads model from URL endpoint.

    Returns
    -------
    None
        This test asserts queue-key model extraction.
    """
    provider = GeminiProvider()
    batcher = Batcher(batch_size=2, batch_window_seconds=10.0, dry_run=True, cache=False)

    queue_key = batcher._build_queue_key(
        provider=provider,
        endpoint="/v1beta/models/gemini-3-flash-preview:generateContent",
        body=b'{"contents":[{"role":"user","parts":[{"text":"hi"}]}]}',
    )

    assert queue_key == (
        "gemini",
        "/v1beta/models/gemini-3-flash-preview:generateContent",
        "gemini-3-flash-preview",
    )


def test_gemini_uses_distinct_submit_poll_and_results_paths() -> None:
    """
    Ensure Gemini exposes separate submit, poll, and results endpoints.

    Returns
    -------
    None
        This test asserts Gemini endpoint path builders.
    """
    provider = GeminiProvider()
    queue_key = (
        "gemini",
        "/v1beta/models/gemini-3-flash-preview:generateContent",
        "gemini-3-flash-preview",
    )

    assert (
        provider.build_batch_submit_path(queue_key=queue_key)
        == "/v1beta/models/gemini-3-flash-preview:batchGenerateContent"
    )
    assert provider.build_batch_poll_path(batch_id="batch-123") == "/v1beta/batches/batch-123"
    assert (
        provider.build_batch_results_path(
            file_id="files/gemini-output-123",
            batch_id="batch-123",
        )
        == "/download/v1beta/files/files/gemini-output-123:download?alt=media"
    )


def test_openai_default_batch_paths_remain_unchanged() -> None:
    """
    Ensure default provider batch path builders keep legacy behavior.

    Returns
    -------
    None
        This test asserts default path builders on OpenAI provider.
    """
    provider = OpenAIProvider()
    queue_key = (
        "openai",
        "/v1/chat/completions",
        "gpt-4o-mini",
    )

    assert provider.build_batch_submit_path(queue_key=queue_key) == "/v1/batches"
    assert provider.build_batch_poll_path(batch_id="batch-123") == "/v1/batches/batch-123"
    assert (
        provider.build_batch_results_path(file_id="file-123", batch_id="batch-123")
        == "/v1/files/file-123/content"
    )


def test_default_batch_status_extraction_uses_top_level_field() -> None:
    """
    Ensure default batch status extraction reads provider status field.

    Returns
    -------
    None
        This test asserts base status extraction behavior.
    """
    provider = OpenAIProvider()

    assert provider.extract_batch_status(payload={"status": "completed"}) == "completed"
    assert provider.extract_batch_status(payload={}) == "created"


def test_gemini_batch_status_extraction_uses_metadata_state_field() -> None:
    """
    Ensure Gemini status extraction reads metadata.state.

    Returns
    -------
    None
        This test asserts Gemini nested status extraction behavior.
    """
    provider = GeminiProvider()

    assert (
        provider.extract_batch_status(payload={"metadata": {"state": "BATCH_STATE_SUCCEEDED"}})
        == "BATCH_STATE_SUCCEEDED"
    )
    assert provider.extract_batch_status(payload={}) == "created"


@pytest.mark.asyncio
async def test_homogeneous_provider_different_models_use_distinct_queues():
    """Test strict batching partitions queues by model."""
    provider = HomogeneousOpenAIProvider()
    batcher = Batcher(batch_size=2, batch_window_seconds=10.0, dry_run=True, cache=False)

    await asyncio.gather(
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
        ),
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
        ),
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-b","messages":[]}',
        ),
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-b","messages":[]}',
        ),
    )

    assert len(batcher._active_batches) == 2
    assert _pending_count_for_provider(batcher=batcher, provider_name=provider.name) == 0
    await batcher.close()


@pytest.mark.asyncio
async def test_homogeneous_provider_missing_model_fails_fast():
    """Test strict batching rejects requests without model."""
    provider = HomogeneousOpenAIProvider()
    batcher = Batcher(batch_size=2, batch_window_seconds=10.0, dry_run=True, cache=False)

    with pytest.raises(ValueError, match="model"):
        await batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"messages":[]}',
        )

    assert _pending_count_for_provider(batcher=batcher, provider_name=provider.name) == 0
    assert len(batcher._pending_by_provider) == 0
    await batcher.close()


@pytest.mark.asyncio
async def test_strict_queue_key_mixed_models_use_distinct_queues():
    """Test strict queue key partitions requests by model."""
    provider = OpenAIProvider()
    batcher = Batcher(batch_size=3, batch_window_seconds=10.0, dry_run=True, cache=False)

    task_1 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
        )
    )
    task_2 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-b","messages":[]}',
        )
    )

    await asyncio.sleep(delay=0.05)

    assert _pending_count_for_provider(batcher=batcher, provider_name=provider.name) == 2
    assert _queue_key(provider_name=provider.name, model_name="model-a") in batcher._window_tasks
    assert _queue_key(provider_name=provider.name, model_name="model-b") in batcher._window_tasks

    await batcher.close()
    await asyncio.gather(task_1, task_2)


@pytest.mark.asyncio
async def test_strict_queue_key_different_endpoints_use_distinct_queues():
    """Test strict queue key partitions requests by endpoint."""
    provider = OpenAIProvider()
    batcher = Batcher(batch_size=3, batch_window_seconds=10.0, dry_run=True, cache=False)

    task_1 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
        )
    )
    task_2 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/embeddings",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
        )
    )

    await asyncio.sleep(delay=0.05)

    assert (
        _queue_key(
            provider_name=provider.name,
            endpoint="/v1/chat/completions",
            model_name="model-a",
        )
        in batcher._window_tasks
    )
    assert (
        _queue_key(
            provider_name=provider.name,
            endpoint="/v1/embeddings",
            model_name="model-a",
        )
        in batcher._window_tasks
    )

    await batcher.close()
    await asyncio.gather(task_1, task_2)


@pytest.mark.asyncio
async def test_close_flushes_all_model_scoped_queues_for_homogeneous_provider():
    """Test close flushes all strict model-scoped queues."""
    provider = HomogeneousOpenAIProvider()
    batcher = Batcher(batch_size=5, batch_window_seconds=10.0, dry_run=True, cache=False)

    task_1 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
        )
    )
    task_2 = asyncio.create_task(
        batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-b","messages":[]}',
        )
    )

    await asyncio.sleep(delay=0.05)

    assert (
        _queue_key(provider_name=provider.name, model_name="model-a")
        in batcher._pending_by_provider
    )
    assert (
        _queue_key(provider_name=provider.name, model_name="model-b")
        in batcher._pending_by_provider
    )

    await batcher.close()
    await asyncio.gather(task_1, task_2)

    assert _pending_count_for_provider(batcher=batcher, provider_name=provider.name) == 0
    assert len(batcher._active_batches) == 2


@pytest.mark.asyncio
async def test_submit_requests_passes_queue_key_to_process_batch():
    """Test _submit_requests forwards queue_key to _process_batch."""
    provider = OpenAIProvider()
    batcher = Batcher(batch_size=2, batch_window_seconds=10.0, dry_run=True, cache=False)
    loop = asyncio.get_running_loop()
    request = _PendingRequest(
        custom_id="request-id",
        queue_key=_queue_key(provider_name=provider.name),
        params={
            "client_type": "httpx",
            "method": "POST",
            "url": "api.openai.com",
            "endpoint": "/v1/chat/completions",
            "body": b'{"model":"model-a","messages":[]}',
        },
        provider=provider,
        future=loop.create_future(),
        request_hash="hash-request-id",
    )
    captured: dict[str, QueueKey] = {}
    called_event = asyncio.Event()

    async def fake_process_batch(*, queue_key: QueueKey, requests: list[_PendingRequest]) -> None:
        captured["queue_key"] = queue_key
        captured["request_queue_key"] = requests[0].queue_key
        called_event.set()

    batcher._process_batch = fake_process_batch  # type: ignore[method-assign]
    queue_key = _queue_key(provider_name=provider.name)
    await batcher._submit_requests(queue_key=queue_key, requests=[request])
    await asyncio.wait_for(called_event.wait(), timeout=1.0)

    assert captured["queue_key"] == queue_key
    assert captured["request_queue_key"] == queue_key


@pytest.mark.asyncio
async def test_process_batch_calls_provider_with_queue_key():
    """Test _process_batch passes queue_key argument to provider.process_batch."""
    provider = HomogeneousOpenAIProvider()
    batcher = Batcher(batch_size=2, batch_window_seconds=10.0, dry_run=False, cache=False)
    loop = asyncio.get_running_loop()
    queue_key = _queue_key(provider_name=provider.name, model_name="model-a")
    request = _PendingRequest(
        custom_id="request-1",
        queue_key=queue_key,
        params={
            "client_type": "httpx",
            "method": "POST",
            "url": "api.openai.com",
            "endpoint": "/v1/chat/completions",
            "body": b'{"model":"model-a","messages":[]}',
            "headers": {},
        },
        provider=provider,
        future=loop.create_future(),
        request_hash="hash-request-1",
    )
    captured: dict[str, QueueKey] = {}

    async def fake_process_batch(
        *,
        requests,
        client_factory,
        queue_key: QueueKey,
    ):
        del requests
        del client_factory
        captured["queue_key"] = queue_key
        raise RuntimeError("provider call captured")

    provider.process_batch = fake_process_batch  # type: ignore[method-assign]
    await batcher._process_batch(queue_key=queue_key, requests=[request])

    assert captured["queue_key"] == queue_key
    with pytest.raises(RuntimeError, match="provider call captured"):
        await request.future


@pytest.mark.asyncio
async def test_mistral_build_file_based_batch_payload_uses_queue_key_model():
    """Test Mistral file-based payload model comes from queue_key."""
    provider = MistralProvider()
    payload = await provider.build_file_based_batch_payload(
        file_id="file-123",
        endpoint="/v1/chat/completions",
        queue_key=_queue_key(provider_name=provider.name, model_name="mistral-small-latest"),
    )
    assert payload["input_files"] == ["file-123"]
    assert payload["endpoint"] == "/v1/chat/completions"
    assert payload["model"] == "mistral-small-latest"


@pytest.mark.asyncio
async def test_process_batch_uses_inline_submission_for_anthropic(monkeypatch):
    """Test Anthropic inline flow skips file upload and submits inline requests."""
    provider = AnthropicProvider()
    queue_key = _queue_key(
        provider_name=provider.name, endpoint="/v1/messages", model_name="claude"
    )
    request = _PendingRequest(
        custom_id="request-1",
        queue_key=queue_key,
        params={
            "client_type": "httpx",
            "method": "POST",
            "url": "api.anthropic.com",
            "endpoint": "/v1/messages",
            "body": b'{"model":"claude","max_tokens":32,"messages":[{"role":"user","content":"hi"}]}',
            "headers": {"X-Api-Key": "test-key"},
        },
        provider=provider,
        future=asyncio.get_running_loop().create_future(),
        request_hash="hash-request-1",
    )
    calls: dict[str, t.Any] = {"uploaded": False, "inline_lines": []}

    async def fail_upload(**_kwargs):
        calls["uploaded"] = True
        raise AssertionError("inline providers should not upload files")

    async def fake_create_inline_batch_job(
        *, base_url, api_headers, jsonl_lines, queue_key, client_factory
    ):
        del client_factory
        calls["queue_key"] = queue_key
        calls["base_url"] = base_url
        calls["api_headers"] = api_headers
        calls["inline_lines"] = jsonl_lines
        return "msgbatch-123"

    monkeypatch.setattr(target=provider, name="_upload_batch_file", value=fail_upload)
    monkeypatch.setattr(
        target=provider,
        name="_create_inline_batch_job",
        value=fake_create_inline_batch_job,
    )

    submission = await provider.process_batch(
        requests=[request],
        client_factory=lambda: httpx.AsyncClient(),
        queue_key=queue_key,
    )

    assert not calls["uploaded"]
    assert calls["base_url"] == "https://api.anthropic.com"
    assert calls["api_headers"]["X-Api-Key"] == "test-key"
    assert calls["api_headers"]["x-batchling-internal"] == "1"
    assert calls["inline_lines"][0]["params"]["model"] == "claude"
    assert calls["queue_key"] == queue_key
    assert submission.batch_id == "msgbatch-123"


@pytest.mark.asyncio
async def test_cache_hit_skips_provider_submission(
    monkeypatch, mock_openai_api_transport: httpx.MockTransport
):
    """Test cache-hit requests bypass provider batch submission."""
    first_batcher = Batcher(batch_size=2, batch_window_seconds=0.1, cache=True)
    first_batcher._client_factory = lambda: httpx.AsyncClient(transport=mock_openai_api_transport)
    first_batcher._poll_interval_seconds = 0.01

    first_provider = OpenAIProvider()
    first_result = await first_batcher.submit(
        client_type="httpx",
        method="POST",
        url="api.openai.com",
        endpoint="/v1/chat/completions",
        provider=first_provider,
        headers={"Authorization": "Bearer token"},
        body=b'{"model":"model-a","messages":[]}',
    )
    assert first_result.status_code == 200
    await first_batcher.close()

    second_batcher = Batcher(batch_size=2, batch_window_seconds=0.1, cache=True)
    second_batcher._client_factory = lambda: httpx.AsyncClient(transport=mock_openai_api_transport)
    second_batcher._poll_interval_seconds = 0.01
    second_provider = OpenAIProvider()

    async def fail_process_batch(**kwargs):
        del kwargs
        raise AssertionError("cache-hit path should not submit a new provider batch")

    monkeypatch.setattr(
        target=second_provider,
        name="process_batch",
        value=fail_process_batch,
    )

    second_result = await second_batcher.submit(
        client_type="httpx",
        method="POST",
        url="api.openai.com",
        endpoint="/v1/chat/completions",
        provider=second_provider,
        headers={"Authorization": "Bearer token"},
        body=b'{"model":"model-a","messages":[]}',
    )
    assert second_result.status_code == 200
    assert len(second_batcher._active_batches) == 0
    await second_batcher.close()


@pytest.mark.asyncio
async def test_cache_route_failure_falls_back_to_fresh_submission(
    mock_openai_api_transport: httpx.MockTransport,
):
    """Test cache-hit poll failure reroutes the request to fresh batching."""
    batcher = Batcher(batch_size=2, batch_window_seconds=0.1, cache=True)
    batcher._client_factory = lambda: httpx.AsyncClient(transport=mock_openai_api_transport)
    batcher._poll_interval_seconds = 0.01
    assert batcher._cache_store is not None

    provider = OpenAIProvider()
    queue_key = ("openai", "/v1/chat/completions", "model-a")
    request_hash = batcher._build_request_hash(
        queue_key=queue_key,
        host="api.openai.com",
        body=b'{"model":"model-a","messages":[]}',
    )
    _ = batcher._cache_store.upsert_many(
        entries=[
            CacheEntry(
                request_hash=request_hash,
                provider="openai",
                endpoint="/v1/chat/completions",
                model="model-a",
                host="api.openai.com",
                batch_id="batch-missing",
                custom_id="custom-missing",
                created_at=time.time(),
            )
        ]
    )

    result = await batcher.submit(
        client_type="httpx",
        method="POST",
        url="api.openai.com",
        endpoint="/v1/chat/completions",
        provider=provider,
        headers={"Authorization": "Bearer token"},
        body=b'{"model":"model-a","messages":[]}',
    )
    assert result.status_code == 200
    await batcher.close()


@pytest.mark.asyncio
async def test_cache_fingerprint_uses_queue_model(
    monkeypatch, mock_openai_api_transport: httpx.MockTransport
):
    """Test model differences do not collide in cache fingerprints."""
    first_batcher = Batcher(batch_size=2, batch_window_seconds=0.1, cache=True)
    first_batcher._client_factory = lambda: httpx.AsyncClient(transport=mock_openai_api_transport)
    first_batcher._poll_interval_seconds = 0.01
    provider = OpenAIProvider()

    _ = await first_batcher.submit(
        client_type="httpx",
        method="POST",
        url="api.openai.com",
        endpoint="/v1/chat/completions",
        provider=provider,
        headers={"Authorization": "Bearer token"},
        body=b'{"model":"model-a","messages":[]}',
    )
    await first_batcher.close()

    second_batcher = Batcher(batch_size=2, batch_window_seconds=0.1, cache=True)
    second_batcher._client_factory = lambda: httpx.AsyncClient(transport=mock_openai_api_transport)
    second_batcher._poll_interval_seconds = 0.01
    second_provider = OpenAIProvider()
    call_count = 0
    original_process_batch = second_provider.process_batch

    async def wrapped_process_batch(*, requests, client_factory, queue_key):
        nonlocal call_count
        call_count += 1
        return await original_process_batch(
            requests=requests,
            client_factory=client_factory,
            queue_key=queue_key,
        )

    monkeypatch.setattr(
        target=second_provider,
        name="process_batch",
        value=wrapped_process_batch,
    )

    _ = await second_batcher.submit(
        client_type="httpx",
        method="POST",
        url="api.openai.com",
        endpoint="/v1/chat/completions",
        provider=second_provider,
        headers={"Authorization": "Bearer token"},
        body=b'{"model":"model-b","messages":[]}',
    )
    assert call_count == 1
    await second_batcher.close()


@pytest.mark.asyncio
async def test_cache_cleanup_removes_rows_older_than_retention(
    mock_openai_api_transport: httpx.MockTransport,
):
    """Test cache cleanup removes entries older than one month."""
    batcher = Batcher(batch_size=2, batch_window_seconds=0.1, cache=True)
    batcher._client_factory = lambda: httpx.AsyncClient(transport=mock_openai_api_transport)
    batcher._poll_interval_seconds = 0.01
    assert batcher._cache_store is not None

    stale_hash = "stale-hash"
    stale_entry = CacheEntry(
        request_hash=stale_hash,
        provider="openai",
        endpoint="/v1/chat/completions",
        model="model-a",
        host="api.openai.com",
        batch_id="batch-stale",
        custom_id="custom-stale",
        created_at=time.time() - (31 * 24 * 60 * 60),
    )
    _ = batcher._cache_store.upsert_many(entries=[stale_entry])

    provider = OpenAIProvider()
    _ = await batcher.submit(
        client_type="httpx",
        method="POST",
        url="api.openai.com",
        endpoint="/v1/chat/completions",
        provider=provider,
        headers={"Authorization": "Bearer token"},
        body=b'{"model":"model-a","messages":[]}',
    )

    assert batcher._cache_store.get_by_hash(request_hash=stale_hash) is None
    await batcher.close()


@pytest.mark.asyncio
async def test_dry_run_cache_hit_is_read_only(mock_openai_api_transport: httpx.MockTransport):
    """Test dry-run mode reads cache hits without writing new cache rows."""
    writer_batcher = Batcher(batch_size=2, batch_window_seconds=0.1, cache=True, dry_run=False)
    writer_batcher._client_factory = lambda: httpx.AsyncClient(transport=mock_openai_api_transport)
    writer_batcher._poll_interval_seconds = 0.01
    provider = OpenAIProvider()

    _ = await writer_batcher.submit(
        client_type="httpx",
        method="POST",
        url="api.openai.com",
        endpoint="/v1/chat/completions",
        provider=provider,
        headers={"Authorization": "Bearer token"},
        body=b'{"model":"model-a","messages":[]}',
    )
    assert writer_batcher._cache_store is not None
    request_hash = writer_batcher._build_request_hash(
        queue_key=("openai", "/v1/chat/completions", "model-a"),
        host="api.openai.com",
        body=b'{"model":"model-a","messages":[]}',
    )
    original_entry = writer_batcher._cache_store.get_by_hash(request_hash=request_hash)
    assert original_entry is not None
    original_created_at = original_entry.created_at
    await writer_batcher.close()

    dry_run_batcher = Batcher(batch_size=2, batch_window_seconds=0.1, cache=True, dry_run=True)
    dry_run_provider = OpenAIProvider()
    dry_run_response = await dry_run_batcher.submit(
        client_type="httpx",
        method="POST",
        url="api.openai.com",
        endpoint="/v1/chat/completions",
        provider=dry_run_provider,
        headers={"Authorization": "Bearer token"},
        body=b'{"model":"model-a","messages":[]}',
    )
    assert dry_run_response.headers["x-batchling-dry-run"] == "1"
    assert dry_run_response.headers["x-batchling-cache-hit"] == "1"
    assert dry_run_response.json()["cache_hit"] is True
    assert dry_run_batcher._cache_store is not None
    dry_run_entry = dry_run_batcher._cache_store.get_by_hash(request_hash=request_hash)
    assert dry_run_entry is not None
    assert dry_run_entry.created_at == original_created_at
    await dry_run_batcher.close()


@pytest.mark.asyncio
async def test_deferred_idle_triggers_deferred_exit():
    """Test deferred mode raises DeferredExit when polling-only idle threshold is reached."""
    batcher = Batcher(
        batch_size=2,
        batch_window_seconds=0.1,
        cache=False,
        deferred=True,
        deferred_idle_seconds=0.01,
    )
    active_task = asyncio.create_task(asyncio.sleep(delay=10.0))
    batcher._batch_tasks.add(active_task)
    batcher._last_intercepted_at = time.time() - 1.0

    await batcher._maybe_trigger_deferred_exit()

    assert isinstance(batcher._deferred_exit_error, DeferredExit)
    with contextlib.suppress(asyncio.CancelledError):
        await active_task
    provider = OpenAIProvider()
    with pytest.raises(DeferredExit):
        await batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=provider,
            body=b'{"model":"model-a","messages":[]}',
        )
