"""
Tests for the batchify function in batchling.batching.api.
"""

import asyncio
import types

import pytest

import batchling.batching.hooks as hooks_module
from batchling.batching.api import batchify
from batchling.batching.core import Batcher
from batchling.batching.hooks import active_batcher
from tests.mocks.clients import (
    MockClient,
    async_function,
    sync_function,
)


@pytest.mark.asyncio
async def test_batchify_installs_hooks(reset_hooks):
    """Test that batchify installs hooks."""
    hooks_module._hooks_installed = False

    _ = batchify(MockClient(), batch_size=10)

    assert hooks_module._hooks_installed is True


@pytest.mark.asyncio
async def test_batchify_creates_batcher(reset_hooks, reset_context):
    """Test that batchify creates a Batcher instance."""
    wrapped = batchify(MockClient(), batch_size=5, batch_window_seconds=1.0)

    assert isinstance(wrapped._self_batcher, Batcher)
    assert wrapped._self_batcher._batch_size == 5
    assert wrapped._self_batcher._batch_window_seconds == 1.0


@pytest.mark.asyncio
async def test_batchify_wraps_object_instance(reset_hooks, reset_context):
    """Test that batchify wraps an object instance with BatchingProxy."""
    client = MockClient()
    wrapped = batchify(client, batch_size=10)

    # Should return a BatchingProxy
    from batchling.batching.proxy import BatchingProxy

    assert isinstance(wrapped, BatchingProxy)
    assert wrapped.__wrapped__ is client


@pytest.mark.asyncio
async def test_batchify_wraps_sync_function(reset_hooks, reset_context):
    """Test that batchify wraps a synchronous function."""
    wrapped_func = batchify(sync_function, batch_size=10)

    # Should return a callable
    assert callable(wrapped_func)
    assert not asyncio.iscoroutinefunction(wrapped_func)

    # Test that it works
    result = wrapped_func(5)
    assert result == 10


@pytest.mark.asyncio
async def test_batchify_wraps_async_function(reset_hooks, reset_context):
    """Test that batchify wraps an asynchronous function."""
    wrapped_func = batchify(async_function, batch_size=10)

    # Should return a coroutine function
    assert callable(wrapped_func)
    assert asyncio.iscoroutinefunction(wrapped_func)

    # Test that it works
    result = await wrapped_func(5)
    assert result == 15


@pytest.mark.asyncio
async def test_batchify_sync_function_sets_context(reset_hooks, reset_context):
    """Test that wrapped sync function sets the batcher context."""
    wrapped_func = batchify(sync_function, batch_size=10)

    # Before calling, context should be None
    assert active_batcher.get() is None

    # Call the wrapped function
    result = wrapped_func(5)

    # After calling, context should be reset to None
    assert active_batcher.get() is None
    assert result == 10


@pytest.mark.asyncio
async def test_batchify_async_function_sets_context(reset_hooks, reset_context):
    """Test that wrapped async function sets the batcher context."""
    wrapped_func = batchify(async_function, batch_size=10)

    # Before calling, context should be None
    assert active_batcher.get() is None

    # Call the wrapped function
    result = await wrapped_func(5)

    # After calling, context should be reset to None
    assert active_batcher.get() is None
    assert result == 15


@pytest.mark.asyncio
async def test_batchify_does_not_wrap_class(reset_hooks, reset_context):
    """Test that batchify does not wrap a class, only instances."""
    wrapped = batchify(MockClient, batch_size=10)

    # Should return a BatchingProxy wrapping the class itself
    from batchling.batching.proxy import BatchingProxy

    assert isinstance(wrapped, BatchingProxy)
    assert wrapped.__wrapped__ is MockClient


@pytest.mark.asyncio
async def test_batchify_preserves_function_metadata(reset_hooks, reset_context):
    """Test that batchify preserves function metadata."""
    wrapped_func = batchify(sync_function, batch_size=10)

    # Should preserve function name
    assert isinstance(wrapped_func, types.FunctionType)
    assert wrapped_func.__name__ == "sync_function"

    # Should preserve docstring
    assert wrapped_func.__doc__ == "Test synchronous function."


@pytest.mark.asyncio
async def test_batchify_handles_exception_in_function(reset_hooks, reset_context):
    """Test that batchify properly resets context even when function raises."""

    def failing_function(x):
        raise ValueError("Test error")

    wrapped_func = batchify(failing_function, batch_size=10)

    # Context should be None before
    assert active_batcher.get() is None

    # Should raise the exception
    with pytest.raises(ValueError, match="Test error"):
        wrapped_func(5)

    # Context should still be reset to None after exception
    assert active_batcher.get() is None


@pytest.mark.asyncio
async def test_batchify_handles_exception_in_async_function(reset_hooks, reset_context):
    """Test that batchify properly resets context even when async function raises."""

    async def failing_async_function(x):
        await asyncio.sleep(0.01)
        raise ValueError("Test error")

    wrapped_func = batchify(failing_async_function, batch_size=10)

    # Context should be None before
    assert active_batcher.get() is None

    # Should raise the exception
    with pytest.raises(ValueError, match="Test error"):
        await wrapped_func(5)

    # Context should still be reset to None after exception
    assert active_batcher.get() is None


@pytest.mark.asyncio
async def test_batchify_idempotent_hooks(reset_hooks):
    """Test that install_hooks is idempotent."""
    # First call
    _ = batchify(MockClient(), batch_size=10)
    original_request = hooks_module._original_httpx_async_request

    # Second call should not change hooks
    _ = batchify(MockClient(), batch_size=10)
    assert hooks_module._original_httpx_async_request is original_request
    assert hooks_module._hooks_installed is True


@pytest.mark.asyncio
async def test_batchify_asyncio_gather_with_wrapped_async_functions(reset_hooks, reset_context):
    """Test that asyncio.gather works correctly with wrapped async functions."""

    # Create a wrapped async function that checks the batcher context
    async def check_context_function(value):
        """Function that checks if batcher context is set."""
        current_batcher = active_batcher.get()
        assert current_batcher is not None, (
            "Batcher context should be set during function execution"
        )
        await asyncio.sleep(0.01)
        return value * 2

    wrapped_func = batchify(check_context_function, batch_size=10)

    # Before gather, context should be None
    assert active_batcher.get() is None

    # Use asyncio.gather to run multiple wrapped functions concurrently
    results = await asyncio.gather(
        wrapped_func(1),
        wrapped_func(2),
        wrapped_func(3),
        wrapped_func(4),
        wrapped_func(5),
    )

    # After gather completes, context should be reset to None
    assert active_batcher.get() is None

    # Verify results
    assert results == [2, 4, 6, 8, 10]


@pytest.mark.asyncio
async def test_batchify_asyncio_gather_context_isolation(reset_hooks, reset_context):
    """Test that each task in asyncio.gather has its own batcher context."""
    # Track which batcher instances are used
    batcher_instances = []

    async def track_batcher_function(value):
        """Function that tracks the batcher instance."""
        current_batcher = active_batcher.get()
        batcher_instances.append(current_batcher)
        await asyncio.sleep(0.01)
        return value

    # Each wrapped function gets its own batcher
    wrapped_func1 = batchify(track_batcher_function, batch_size=10)
    wrapped_func2 = batchify(track_batcher_function, batch_size=20)
    wrapped_func3 = batchify(track_batcher_function, batch_size=30)

    # Before gather, context should be None
    assert active_batcher.get() is None

    # Run gather with different wrapped functions (each has its own batcher)
    results = await asyncio.gather(
        wrapped_func1(1),
        wrapped_func2(2),
        wrapped_func3(3),
    )

    # After gather completes, context should be reset to None
    assert active_batcher.get() is None

    # Verify results
    assert results == [1, 2, 3]

    # Each function should have had a batcher context set
    assert len(batcher_instances) == 3
    # Each batcher should be different (different instances)
    assert batcher_instances[0] is not None
    assert batcher_instances[1] is not None
    assert batcher_instances[2] is not None


@pytest.mark.asyncio
async def test_batchify_asyncio_gather_with_exception(reset_hooks, reset_context):
    """Test that asyncio.gather properly resets context even when one task fails."""

    async def failing_function(value):
        """Function that fails for value 3."""
        current_batcher = active_batcher.get()
        assert current_batcher is not None, "Batcher context should be set"
        await asyncio.sleep(0.01)
        if value == 3:
            raise ValueError(f"Failed for {value}")
        return value * 2

    wrapped_func = batchify(failing_function, batch_size=10)

    # Before gather, context should be None
    assert active_batcher.get() is None

    # Use asyncio.gather - one task will fail
    with pytest.raises(ValueError, match="Failed for 3"):
        await asyncio.gather(
            wrapped_func(1),
            wrapped_func(2),
            wrapped_func(3),  # This will fail
            wrapped_func(4),
        )

    # After gather completes (with exception), context should still be reset to None
    assert active_batcher.get() is None


@pytest.mark.asyncio
async def test_batchify_asyncio_gather_with_return_exceptions(reset_hooks, reset_context):
    """Test that asyncio.gather with return_exceptions=True properly manages context."""

    async def mixed_function(value):
        """Function that fails for value 3."""
        current_batcher = active_batcher.get()
        assert current_batcher is not None, "Batcher context should be set"
        await asyncio.sleep(0.01)
        if value == 3:
            raise ValueError(f"Failed for {value}")
        return value * 2

    wrapped_func = batchify(mixed_function, batch_size=10)

    # Before gather, context should be None
    assert active_batcher.get() is None

    # Use asyncio.gather with return_exceptions=True
    results = await asyncio.gather(
        wrapped_func(1),
        wrapped_func(2),
        wrapped_func(3),  # This will fail but exception is returned
        wrapped_func(4),
        return_exceptions=True,
    )

    # After gather completes, context should be reset to None
    assert active_batcher.get() is None

    # Verify results - first, second, and fourth should be successful
    assert results[0] == 2
    assert results[1] == 4
    assert isinstance(results[2], ValueError)
    assert results[3] == 8
