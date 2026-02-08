"""
Tests for the BatchingProxy class in batchling.batching.proxy.
"""

import asyncio
import typing as t
import warnings
from unittest.mock import AsyncMock, patch

import pytest

from batchling.batching.core import Batcher
from batchling.batching.hooks import active_batcher
from batchling.batching.proxy import BatchingProxy
from tests.mocks.clients import MockClient, MockNested


@pytest.fixture
def batcher():
    """Create a Batcher instance for testing."""
    return Batcher(batch_size=10, batch_window_seconds=1.0)


@pytest.mark.asyncio
async def test_batching_proxy_initialization(batcher):
    """Test that BatchingProxy initializes correctly."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    assert proxy.__wrapped__ is client
    assert proxy._self_batcher is batcher


@pytest.mark.asyncio
async def test_batching_proxy_preserves_attributes(batcher):
    """Test that BatchingProxy preserves wrapped object attributes."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    assert proxy.value == 42
    assert proxy.attr == "test"


@pytest.mark.asyncio
async def test_batching_proxy_wraps_sync_method(batcher, reset_context):
    """Test that BatchingProxy wraps synchronous methods."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    # Before calling, context should be None
    assert active_batcher.get() is None

    # Call the wrapped method
    result = proxy.sync_method(5)

    # After calling, context should be reset to None
    assert active_batcher.get() is None
    assert result == 10


@pytest.mark.asyncio
async def test_batching_proxy_wraps_async_method(batcher, reset_context):
    """Test that BatchingProxy wraps asynchronous methods."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    # Before calling, context should be None
    assert active_batcher.get() is None

    # Call the wrapped method
    result = await proxy.async_method(5)

    # After calling, context should be reset to None
    assert active_batcher.get() is None
    assert result == 15


@pytest.mark.asyncio
async def test_batching_proxy_sets_context_on_method_call(batcher, reset_context):
    """Test that BatchingProxy sets the batcher context during method calls."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    # Create a method that checks the context
    async def check_context_method():
        current_batcher = active_batcher.get()
        assert current_batcher is batcher
        return current_batcher

    # Temporarily add the method to the client
    client.check_context = check_context_method

    # Call through proxy
    result = await proxy.check_context()
    assert result is batcher


@pytest.mark.asyncio
async def test_batching_proxy_recursive_wrapping(batcher, reset_context):
    """Test that BatchingProxy recursively wraps nested objects."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    # Access nested object
    nested = proxy.nested

    # Should return a BatchingProxy
    assert isinstance(nested, BatchingProxy)
    assert isinstance(nested.__wrapped__, MockNested)

    # Should be able to call nested methods
    result = nested.sync_nested(5)
    assert result == 15


@pytest.mark.asyncio
async def test_batching_proxy_handles_dunder_methods(batcher):
    """Test that BatchingProxy properly handles dunder methods."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    # Dunder methods should work through the proxy
    # wrapt.ObjectProxy wraps them but delegates correctly
    assert str(proxy) == "MockClient"
    # repr will show the proxy wrapper, which is expected behavior
    assert "MockClient" in repr(proxy) or "BatchingProxy" in repr(proxy)

    # Should work normally
    assert hasattr(proxy, "__str__")
    assert hasattr(proxy, "__repr__")


@pytest.mark.asyncio
async def test_batching_proxy_does_not_wrap_basic_types(batcher):
    """Test that BatchingProxy does not wrap basic types."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    # Basic types should be returned as-is
    assert isinstance(proxy.value, int)
    assert proxy.value == 42
    assert isinstance(proxy.attr, str)
    assert proxy.attr == "test"


@pytest.mark.asyncio
async def test_batching_proxy_handles_exception_in_method(batcher, reset_context):
    """Test that BatchingProxy properly resets context even when method raises."""
    client = MockClient()

    def failing_method():
        raise ValueError("Test error")

    client.failing_method = failing_method
    proxy = BatchingProxy(client, batcher)

    # Context should be None before
    assert active_batcher.get() is None

    # Should raise the exception
    with pytest.raises(ValueError, match="Test error"):
        proxy.failing_method()

    # Context should still be reset to None after exception
    assert active_batcher.get() is None


@pytest.mark.asyncio
async def test_batching_proxy_handles_exception_in_async_method(batcher, reset_context):
    """Test that BatchingProxy properly resets context even when async method raises."""
    client = MockClient()

    async def failing_async_method():
        await asyncio.sleep(0.01)
        raise ValueError("Test error")

    client.failing_async_method = failing_async_method
    proxy = BatchingProxy(client, batcher)

    # Context should be None before
    assert active_batcher.get() is None

    # Should raise the exception
    with pytest.raises(ValueError, match="Test error"):
        await proxy.failing_async_method()

    # Context should still be reset to None after exception
    assert active_batcher.get() is None


@pytest.mark.asyncio
async def test_batching_proxy_sync_context_manager(batcher, reset_context):
    """Test that BatchingProxy works as a sync context manager."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    # Mock the close method to avoid actual async cleanup
    with patch.object(batcher, "close", new_callable=AsyncMock):
        with proxy:
            # Should be able to use proxy inside context
            assert active_batcher.get() is batcher
            assert proxy.value == 42
        assert active_batcher.get() is None


@pytest.mark.asyncio
async def test_batching_proxy_sync_context_manager_warns_without_loop(batcher, reset_context):
    """Test that sync context manager warns when no event loop is running."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    # Ensure no event loop is running
    try:
        _ = asyncio.get_running_loop()
        # If we're here, there's a loop, so skip this test
        skip = t.cast(t.Callable[[str], t.NoReturn], pytest.skip)
        skip("Event loop is already running")
    except RuntimeError:
        pass

    # Should warn when exiting sync context manager
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        with proxy:
            assert active_batcher.get() is batcher

        # Should have a warning
        assert len(w) > 0
        assert any("sync context manager" in str(warning.message).lower() for warning in w)
    assert active_batcher.get() is None


@pytest.mark.asyncio
async def test_batching_proxy_async_context_manager(batcher, reset_context):
    """Test that BatchingProxy works as an async context manager."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    # Mock the close method
    with patch.object(batcher, "close", new_callable=AsyncMock) as mock_close:
        async with proxy:
            # Should be able to use proxy inside context
            assert active_batcher.get() is batcher
            assert proxy.value == 42
        assert active_batcher.get() is None

        # Should have called close
        mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_batching_proxy_async_context_manager_closes_batcher(batcher):
    """Test that async context manager properly closes the batcher."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    # Track if close was called
    close_called = False

    async def mock_close():
        nonlocal close_called
        close_called = True

    batcher.close = mock_close

    async with proxy:
        pass

    assert close_called is True


@pytest.mark.asyncio
async def test_batching_proxy_preserves_isinstance(batcher):
    """Test that BatchingProxy preserves isinstance checks."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    # isinstance should work correctly
    assert isinstance(proxy, BatchingProxy)
    # The wrapped object should still be a MockClient
    assert isinstance(proxy.__wrapped__, MockClient)


@pytest.mark.asyncio
async def test_batching_proxy_preserves_method_metadata(batcher):
    """Test that BatchingProxy preserves method metadata."""
    client = MockClient()
    proxy = BatchingProxy(client, batcher)

    # Get the wrapped method
    wrapped_method = proxy.sync_method

    # Should preserve function name
    assert wrapped_method.__name__ == "sync_method"

    # Should preserve docstring
    assert wrapped_method.__doc__ == "Synchronous method."


@pytest.mark.asyncio
async def test_batching_proxy_multiple_nested_levels(batcher, reset_context):
    """Test that BatchingProxy handles multiple levels of nesting."""

    class Level1:
        @property
        def level2(self):
            return Level2()

    class Level2:
        @property
        def level3(self):
            return Level3()

    class Level3:
        def method(self):
            return "deep"

    client = Level1()
    proxy = BatchingProxy(client, batcher)

    # Should recursively wrap all levels
    level2 = proxy.level2
    assert isinstance(level2, BatchingProxy)

    level3 = level2.level3
    assert isinstance(level3, BatchingProxy)

    result = level3.method()
    assert result == "deep"


@pytest.mark.asyncio
async def test_batching_proxy_passes_arguments_correctly(batcher, reset_context):
    """Test that BatchingProxy passes arguments correctly to wrapped methods."""
    client = MockClient()

    def method_with_args(a, b, c=10):
        return a + b + c

    async def async_method_with_args(a, b, c=10):
        await asyncio.sleep(0.01)
        return a + b + c

    client.method_with_args = method_with_args
    client.async_method_with_args = async_method_with_args

    proxy = BatchingProxy(client, batcher)

    # Test sync method
    result = proxy.method_with_args(1, 2, c=3)
    assert result == 6

    # Test async method
    result = await proxy.async_method_with_args(1, 2, c=3)
    assert result == 6
