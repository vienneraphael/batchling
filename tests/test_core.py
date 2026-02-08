"""
Tests for the Batcher class in batchling.batching.core.
"""

import asyncio

import httpx
import pytest

from batchling.batching.core import Batcher

OPENAI_BASE_URL = "https://api.openai.com/v1"


@pytest.fixture
def batcher():
    """Create a Batcher instance for testing."""
    return Batcher(batch_size=3, batch_window_seconds=0.5)


@pytest.fixture
def fast_batcher():
    """Create a Batcher with a very short window for fast tests."""
    return Batcher(batch_size=2, batch_window_seconds=0.1)


@pytest.mark.asyncio
async def test_batcher_initialization():
    """Test that Batcher initializes with correct parameters."""
    batcher = Batcher(batch_size=10, batch_window_seconds=2.0)

    assert batcher._batch_size == 10
    assert batcher._batch_window_seconds == 2.0
    assert len(batcher._pending) == 0
    assert len(batcher._active_batches) == 0
    assert batcher._window_task is None


@pytest.mark.asyncio
async def test_submit_single_request(batcher):
    """Test submitting a single request."""
    result = await batcher.submit(
        client_type="httpx",
        method="GET",
        url=f"{OPENAI_BASE_URL}/test",
    )

    # Currently returns a placeholder response as batch submission is not implemented
    assert isinstance(result, httpx.Response)
    assert result.status_code == 400
    assert len(batcher._pending) == 0
    assert len(batcher._active_batches) == 1


@pytest.mark.asyncio
async def test_submit_multiple_requests_queued(batcher):
    """Test that multiple requests are queued before batch size is reached."""
    # Submit 2 requests (less than batch_size=3)
    task1 = asyncio.create_task(batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/1"))
    task2 = asyncio.create_task(batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/2"))

    # Give a small delay to ensure requests are queued
    await asyncio.sleep(0.05)

    # Should have 2 pending requests
    assert len(batcher._pending) == 2
    assert batcher._window_task is not None

    # Wait for both tasks to complete
    await task1
    await task2


@pytest.mark.asyncio
async def test_batch_size_threshold_triggers_submission(batcher):
    """Test that batch submission is triggered when batch_size is reached."""
    results = await asyncio.gather(
        batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/1"),
        batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/2"),
        batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/3"),
    )

    # All requests should complete
    assert all(isinstance(r, httpx.Response) and r.status_code == 400 for r in results)

    # Pending queue should be empty (batch was submitted)
    assert len(batcher._pending) == 0

    # Should have one active batch
    assert len(batcher._active_batches) == 1

    # Window task should be cancelled/None
    assert batcher._window_task is None or batcher._window_task.done()


@pytest.mark.asyncio
async def test_window_time_triggers_submission(fast_batcher):
    """Test that batch submission is triggered after window time elapses."""
    # Submit 1 request (less than batch_size=2)
    task = asyncio.create_task(fast_batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/1"))

    # Wait for window time to elapse (0.1 seconds)
    await asyncio.sleep(0.15)

    # Request should complete
    result = await task
    assert isinstance(result, httpx.Response)
    assert result.status_code == 400

    # Pending queue should be empty
    assert len(fast_batcher._pending) == 0

    # Should have one active batch
    assert len(fast_batcher._active_batches) == 1


@pytest.mark.asyncio
async def test_window_timer_cancelled_on_size_threshold(batcher):
    """Test that window timer is cancelled when batch size threshold is reached."""
    # Submit 2 requests to start the timer
    task1 = asyncio.create_task(batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/1"))
    task2 = asyncio.create_task(batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/2"))

    await asyncio.sleep(0.05)

    # Timer should be running
    assert batcher._window_task is not None
    assert not batcher._window_task.done()

    # Submit third request to trigger size threshold
    task3 = asyncio.create_task(batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/3"))

    await asyncio.gather(task1, task2, task3)

    # Timer should be cancelled/None
    assert batcher._window_task is None or batcher._window_task.done()


@pytest.mark.asyncio
async def test_multiple_batches_submitted(fast_batcher):
    """Test that multiple batches can be submitted sequentially."""
    # Submit first batch (size threshold)
    await asyncio.gather(
        fast_batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/1"),
        fast_batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/2"),
    )

    # Submit second batch (size threshold)
    await asyncio.gather(
        fast_batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/3"),
        fast_batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/4"),
    )

    # Should have 2 active batches
    assert len(fast_batcher._active_batches) == 2
    assert len(fast_batcher._pending) == 0


@pytest.mark.asyncio
async def test_concurrent_requests(batcher):
    """Test handling of concurrent requests."""
    # Submit 5 requests concurrently (will create 2 batches)
    tasks = [
        asyncio.create_task(batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/{i}"))
        for i in range(5)
    ]

    results = await asyncio.gather(*tasks)

    # All should complete
    assert all(isinstance(r, httpx.Response) and r.status_code == 400 for r in results)

    # Should have 2 batches (3 + 2)
    assert len(batcher._active_batches) == 2
    assert len(batcher._pending) == 0


@pytest.mark.asyncio
async def test_submit_with_kwargs(batcher):
    """Test that submit accepts and stores kwargs."""
    result = await batcher.submit(
        client_type="httpx",
        method="POST",
        url=f"{OPENAI_BASE_URL}/api",
        json={"key": "value"},
        headers={"Authorization": "Bearer token"},
    )

    assert isinstance(result, httpx.Response)
    assert result.status_code == 400

    # Check that the batch contains the request with kwargs
    assert len(batcher._active_batches) == 1
    batch = batcher._active_batches[0]
    assert len(batch.requests) == 1

    request = list(batch.requests.values())[0]
    assert request.params["method"] == "POST"
    assert request.params["url"] == f"{OPENAI_BASE_URL}/api"
    assert request.params["json"] == {"key": "value"}
    assert request.params["headers"] == {"Authorization": "Bearer token"}


@pytest.mark.asyncio
async def test_close_submits_remaining_requests(fast_batcher):
    """Test that close() submits any remaining pending requests."""
    # Submit 1 request (less than batch_size)
    task = asyncio.create_task(fast_batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/1"))

    # Don't wait for window, close immediately
    await asyncio.sleep(0.05)

    # Close should submit the pending request
    await fast_batcher.close()

    # Request should complete
    result = await task
    assert isinstance(result, httpx.Response)
    assert result.status_code == 400

    # Pending should be empty
    assert len(fast_batcher._pending) == 0


@pytest.mark.asyncio
async def test_close_cancels_window_timer(fast_batcher):
    """Test that close() cancels the window timer."""
    # Submit 1 request to start timer
    task = asyncio.create_task(fast_batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/1"))

    await asyncio.sleep(0.05)

    # Timer should be running
    assert fast_batcher._window_task is not None
    assert not fast_batcher._window_task.done()

    # Close should cancel timer and submit batch
    await fast_batcher.close()

    # Timer should be cancelled
    assert fast_batcher._window_task is None or fast_batcher._window_task.done()

    # Request should complete
    await task


@pytest.mark.asyncio
async def test_batch_submission_error_handling(batcher):
    """Test that errors during batch submission fail all pending futures."""
    # Patch _submit_batch to raise an error
    original_submit = batcher._submit_batch

    async def failing_submit():
        raise Exception("Batch submission failed")

    batcher._submit_batch = failing_submit
    try:
        # Submit requests
        task1 = asyncio.create_task(batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/1"))
        task2 = asyncio.create_task(batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/2"))
        task3 = asyncio.create_task(batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/3"))

        # All should fail with the error
        with pytest.raises(Exception, match="Batch submission failed"):
            await asyncio.gather(task1, task2, task3, return_exceptions=False)
    finally:
        batcher._submit_batch = original_submit


@pytest.mark.asyncio
async def test_window_timer_error_handling(fast_batcher):
    """Test that errors in window timer fail pending futures.

    This tests the error handler in _window_timer. If _submit_batch raises an
    exception (before its own try/except can catch it), _window_timer's error
    handler will catch it, fail all pending futures, and then re-raise.

    Note: In normal operation, _submit_batch has its own error handling, so this
    scenario is rare. But the error handler exists as defensive code.
    """

    # Make _submit_batch raise an error immediately (before its try/except)
    async def failing_submit():
        # Raise before _submit_batch's try/except can catch it
        raise Exception("Timer error during batch submission")

    fast_batcher._submit_batch = failing_submit

    # Submit a request - the window timer will trigger and call _submit_batch
    # The exception will propagate to _window_timer's error handler
    task = asyncio.create_task(fast_batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/1"))

    # Wait for the window timer to trigger (0.1 seconds)
    await asyncio.sleep(0.15)

    # The task should fail with the error
    # The _window_timer error handler catches it, fails the future, then re-raises
    with pytest.raises(Exception, match="Timer error during batch submission"):
        await task

    # Verify the task completed (even though it failed)
    assert task.done()


@pytest.mark.asyncio
async def test_empty_batch_not_submitted(batcher):
    """Test that submitting an empty batch does nothing."""
    # Call _submit_batch directly with no pending requests
    await batcher._submit_batch()

    # Should have no active batches
    assert len(batcher._active_batches) == 0


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_custom_id_uniqueness(batcher):
    """Test that each request gets a unique custom_id."""
    # Submit multiple requests
    await asyncio.gather(
        batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/1"),
        batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/2"),
        batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/3"),
    )

    # Get all custom_ids from the batch
    batch = batcher._active_batches[0]
    custom_ids = list(batch.requests.keys())

    # All should be unique
    assert len(custom_ids) == len(set(custom_ids))
    assert len(custom_ids) == 3


@pytest.mark.asyncio
async def test_active_batch_tracking(batcher):
    """Test that active batches are properly tracked."""
    # Submit a batch
    await asyncio.gather(
        batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/1"),
        batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/2"),
        batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/3"),
    )

    # Check batch properties
    assert len(batcher._active_batches) == 1
    batch = batcher._active_batches[0]

    assert batch.batch_id is not None
    assert isinstance(batch.created_at, float)
    assert batch.created_at > 0
    assert len(batch.requests) == 3


@pytest.mark.asyncio
async def test_multiple_windows_sequential(fast_batcher):
    """Test that multiple windows work sequentially."""
    # First window: submit 1 request, wait for window
    task1 = asyncio.create_task(fast_batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/1"))
    await asyncio.sleep(0.15)
    await task1

    # Second window: submit 1 request, wait for window
    task2 = asyncio.create_task(fast_batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/2"))
    await asyncio.sleep(0.15)
    await task2

    # Should have 2 batches
    assert len(fast_batcher._active_batches) == 2


@pytest.mark.asyncio
async def test_large_batch_size(fast_batcher):
    """Test with a larger batch size."""
    large_batcher = Batcher(batch_size=10, batch_window_seconds=0.1)

    # Submit 10 requests to trigger size threshold
    tasks = [
        asyncio.create_task(large_batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/{i}"))
        for i in range(10)
    ]

    results = await asyncio.gather(*tasks)
    assert all(isinstance(r, httpx.Response) and r.status_code == 400 for r in results)
    assert len(large_batcher._active_batches) == 1
    assert len(large_batcher._pending) == 0


@pytest.mark.asyncio
async def test_close_idempotent(batcher):
    """Test that close() can be called multiple times safely."""
    await batcher.close()
    await batcher.close()
    await batcher.close()

    # Should not raise any errors
    assert True


@pytest.mark.asyncio
async def test_submit_after_close(batcher):
    """Test behavior when submitting after close."""
    await batcher.close()

    # Submitting after close should still work (batcher is not fully closed)
    # The batcher doesn't prevent new submissions after close
    result = await batcher.submit("httpx", "GET", f"{OPENAI_BASE_URL}/1")
    assert isinstance(result, httpx.Response)
    assert result.status_code == 400
