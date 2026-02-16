"""
Tests for the Batcher class in batchling.batching.core.
"""

import asyncio

import httpx
import pytest

from batchling.batching.core import Batcher, _PendingRequest
from batchling.batching.providers.mistral import MistralProvider
from batchling.batching.providers.openai import OpenAIProvider
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
    batcher = Batcher(batch_size=3, batch_window_seconds=0.5)
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
    batcher = Batcher(batch_size=2, batch_window_seconds=0.1)
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
    large_batcher = Batcher(batch_size=10, batch_window_seconds=0.1)
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
    batcher = Batcher(batch_size=2, batch_window_seconds=10.0, dry_run=True)

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
    batcher = Batcher(batch_size=3, batch_window_seconds=10.0, dry_run=True)

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
    batcher = Batcher(batch_size=3, batch_window_seconds=10.0, dry_run=True)

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


@pytest.mark.asyncio
async def test_homogeneous_provider_different_models_use_distinct_queues():
    """Test strict batching partitions queues by model."""
    provider = HomogeneousOpenAIProvider()
    batcher = Batcher(batch_size=2, batch_window_seconds=10.0, dry_run=True)

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
    batcher = Batcher(batch_size=2, batch_window_seconds=10.0, dry_run=True)

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
    batcher = Batcher(batch_size=3, batch_window_seconds=10.0, dry_run=True)

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
    batcher = Batcher(batch_size=3, batch_window_seconds=10.0, dry_run=True)

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
    batcher = Batcher(batch_size=5, batch_window_seconds=10.0, dry_run=True)

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
    batcher = Batcher(batch_size=2, batch_window_seconds=10.0, dry_run=True)
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
    batcher = Batcher(batch_size=2, batch_window_seconds=10.0, dry_run=False)
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
async def test_mistral_build_batch_payload_uses_queue_key_model():
    """Test Mistral payload model comes from queue_key."""
    provider = MistralProvider()
    payload = await provider._build_batch_payload(
        file_id="file-123",
        endpoint="/v1/chat/completions",
        queue_key=_queue_key(provider_name=provider.name, model_name="mistral-small-latest"),
    )
    assert payload["model"] == "mistral-small-latest"


@pytest.mark.asyncio
async def test_mistral_build_batch_payload_without_model_fails():
    """Test Mistral payload build fails when queue_key has no model."""
    provider = MistralProvider()
    with pytest.raises(ValueError, match="queue key"):
        await provider._build_batch_payload(
            file_id="file-123",
            endpoint="/v1/chat/completions",
            queue_key=(
                provider.name,
                "/v1/chat/completions",
                "",
            ),
        )
