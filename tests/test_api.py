"""Tests for the batchify function in batchling.batching.api."""

from unittest.mock import AsyncMock, patch

import pytest

import batchling.batching.hooks as hooks_module
from batchling.batching.api import batchify
from batchling.batching.core import Batcher
from batchling.batching.hooks import active_batcher
from tests.mocks.clients import (
    MockClient,
    sync_function,
)


@pytest.mark.asyncio
async def test_batchify_installs_hooks(reset_hooks):
    """Test that batchify installs hooks."""
    hooks_module._hooks_installed = False

    _ = batchify(target=MockClient(), batch_size=10)

    assert hooks_module._hooks_installed is True


@pytest.mark.asyncio
async def test_batchify_creates_batcher(reset_hooks, reset_context):
    """Test that batchify creates a Batcher instance."""
    wrapped = batchify(
        target=MockClient(),
        batch_size=5,
        batch_window_seconds=1.0,
    )

    assert isinstance(wrapped._self_batcher, Batcher)
    assert wrapped._self_batcher._batch_size == 5
    assert wrapped._self_batcher._batch_window_seconds == 1.0


@pytest.mark.asyncio
async def test_batchify_creates_dry_run_batcher(reset_hooks, reset_context):
    """Test that batchify forwards the dry_run flag to Batcher."""
    wrapped = batchify(
        target=MockClient(),
        batch_size=5,
        batch_window_seconds=1.0,
        dry_run=True,
    )

    assert isinstance(wrapped._self_batcher, Batcher)
    assert wrapped._self_batcher._dry_run is True


@pytest.mark.asyncio
async def test_batchify_wraps_object_instance(reset_hooks, reset_context):
    """Test that batchify wraps an object instance with BatchingContext."""
    client = MockClient()
    wrapped = batchify(target=client, batch_size=10)

    # Should return a BatchingContext
    from batchling.batching.context import BatchingContext

    assert isinstance(wrapped, BatchingContext)
    assert wrapped._self_target is client


@pytest.mark.asyncio
async def test_batchify_without_target_returns_context(reset_hooks, reset_context):
    """Test that batchify returns a context manager when no target is supplied."""
    wrapped = batchify()

    from batchling.batching.context import BatchingContext

    assert isinstance(wrapped, BatchingContext)

    with patch.object(
        target=wrapped._self_batcher,
        attribute="close",
        new_callable=AsyncMock,
    ):
        async with wrapped as active_target:
            assert active_batcher.get() is wrapped._self_batcher
            assert active_target is None
        assert active_batcher.get() is None


@pytest.mark.asyncio
async def test_batchify_rejects_class_target(reset_hooks, reset_context):
    """Test that batchify rejects class targets because they are callable."""
    with pytest.raises(expected_exception=TypeError, match="no longer supports callable"):
        _ = batchify(target=MockClient, batch_size=10)


@pytest.mark.asyncio
async def test_batchify_idempotent_hooks(reset_hooks):
    """Test that install_hooks is idempotent."""
    # First call
    _ = batchify(target=MockClient(), batch_size=10)
    original_request = hooks_module._original_httpx_async_send

    # Second call should not change hooks
    _ = batchify(target=MockClient(), batch_size=10)
    assert hooks_module._original_httpx_async_send is original_request
    assert hooks_module._hooks_installed is True


@pytest.mark.asyncio
async def test_batchify_rejects_bound_method(reset_hooks, reset_context):
    """Test that batchify rejects bound methods."""
    client = MockClient()

    with pytest.raises(expected_exception=TypeError, match="no longer supports callable"):
        _ = batchify(target=client.sync_method, batch_size=10)


@pytest.mark.asyncio
async def test_batchify_rejects_sync_function(reset_hooks, reset_context):
    """Test that batchify rejects synchronous callable targets."""
    with pytest.raises(expected_exception=TypeError, match="no longer supports callable"):
        _ = batchify(target=sync_function, batch_size=10)
