"""Tests for the batchify function in batchling.batching.api."""

from unittest.mock import AsyncMock, patch

import pytest

import batchling.hooks as hooks_module
from batchling.api import batchify
from batchling.core import Batcher
from batchling.hooks import active_batcher


@pytest.mark.asyncio
async def test_batchify_installs_hooks(reset_hooks):
    """Test that batchify installs hooks."""
    hooks_module._hooks_installed = False

    _ = batchify(batch_size=10)

    assert hooks_module._hooks_installed is True


@pytest.mark.asyncio
async def test_batchify_creates_batcher(reset_hooks, reset_context):
    """Test that batchify creates a Batcher instance."""
    wrapped = batchify(
        batch_size=5,
        batch_window_seconds=1.0,
    )

    assert isinstance(wrapped._self_batcher, Batcher)
    assert wrapped._self_batcher._batch_size == 5
    assert wrapped._self_batcher._batch_window_seconds == 1.0
    assert wrapped._self_batcher._cache_enabled is True


@pytest.mark.asyncio
async def test_batchify_creates_dry_run_batcher(reset_hooks, reset_context):
    """Test that batchify forwards the dry_run flag to Batcher."""
    wrapped = batchify(
        batch_size=5,
        batch_window_seconds=1.0,
        dry_run=True,
    )

    assert isinstance(wrapped._self_batcher, Batcher)
    assert wrapped._self_batcher._dry_run is True
    assert wrapped._self_batcher._cache_enabled is True
    assert wrapped._self_batcher._cache_write_enabled is False


@pytest.mark.asyncio
async def test_batchify_configures_cache_flag(reset_hooks, reset_context):
    """Test that batchify forwards cache options to Batcher."""
    wrapped = batchify(
        cache=False,
    )

    assert isinstance(wrapped._self_batcher, Batcher)
    assert wrapped._self_batcher._cache_enabled is False


@pytest.mark.asyncio
async def test_batchify_returns_context_manager(reset_hooks, reset_context):
    """Test that batchify returns a BatchingContext."""
    wrapped = batchify(batch_size=10)

    from batchling.context import BatchingContext

    assert isinstance(wrapped, BatchingContext)


@pytest.mark.asyncio
async def test_batchify_without_target_returns_context(reset_hooks, reset_context):
    """Test that batchify returns a context manager that yields None."""
    wrapped = batchify()

    from batchling.context import BatchingContext

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
async def test_batchify_idempotent_hooks(reset_hooks):
    """Test that install_hooks is idempotent."""
    _ = batchify(batch_size=10)
    original_request = hooks_module._original_httpx_async_send

    _ = batchify(batch_size=10)
    assert hooks_module._original_httpx_async_send is original_request
    assert hooks_module._hooks_installed is True


@pytest.mark.asyncio
async def test_batchify_rejects_target_keyword(reset_hooks, reset_context):
    """Test that legacy target keyword is rejected."""
    with pytest.raises(expected_exception=TypeError, match="unexpected keyword argument 'target'"):
        _ = batchify(target=object(), batch_size=10)  # type: ignore[call-arg]
