"""
Tests for the BatchingContext class in batchling.batching.context.
"""

import asyncio
import typing as t
import warnings
from unittest.mock import AsyncMock, patch

import pytest

from batchling.batching.context import BatchingContext
from batchling.batching.core import Batcher
from batchling.batching.hooks import active_batcher
from tests.mocks.clients import MockClient


@pytest.fixture
def batcher() -> Batcher:
    """Create a Batcher instance for testing."""
    return Batcher(batch_size=10, batch_window_seconds=1.0)


def test_batching_context_initialization(batcher: Batcher) -> None:
    """Test that BatchingContext initializes correctly."""
    client = MockClient()
    context = BatchingContext(target=client, batcher=batcher)

    assert context._self_target is client
    assert context._self_batcher is batcher


def test_batching_context_enters_and_exits_sync(batcher: Batcher, reset_context: None) -> None:
    """Test that BatchingContext activates the batcher in a sync scope."""
    client = MockClient()
    context = BatchingContext(target=client, batcher=batcher)

    assert active_batcher.get() is None

    with patch.object(target=batcher, attribute="close", new_callable=AsyncMock):
        with context as active_client:
            assert active_batcher.get() is batcher
            assert active_client is client
        assert active_batcher.get() is None


def test_batching_context_sync_warns_without_loop(
    batcher: Batcher,
    reset_context: None,
) -> None:
    """Test that sync context manager warns when no event loop is running."""
    client = MockClient()
    context = BatchingContext(target=client, batcher=batcher)

    try:
        _ = asyncio.get_running_loop()
        skip = t.cast(typ=t.Callable[[str], t.NoReturn], val=pytest.skip)
        skip("Event loop is already running")
    except RuntimeError:
        pass

    with warnings.catch_warnings(record=True) as warnings_list:
        warnings.simplefilter(action="always")
        with context as active_client:
            assert active_batcher.get() is batcher
            assert active_client is client

        assert len(warnings_list) > 0
        assert any(
            "sync context manager" in str(warning.message).lower() for warning in warnings_list
        )
    assert active_batcher.get() is None


@pytest.mark.asyncio
async def test_batching_context_async_closes_batcher(
    batcher: Batcher,
    reset_context: None,
) -> None:
    """Test that async context manager closes the batcher."""
    client = MockClient()
    context = BatchingContext(target=client, batcher=batcher)

    with patch.object(
        target=batcher,
        attribute="close",
        new_callable=AsyncMock,
    ) as mock_close:
        async with context as active_client:
            assert active_batcher.get() is batcher
            assert active_client is client
        assert active_batcher.get() is None

        mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_batching_context_without_target(batcher: Batcher, reset_context: None) -> None:
    """Test that BatchingContext yields None when no target is supplied."""
    context = BatchingContext(target=None, batcher=batcher)

    async with context as active_target:
        assert active_batcher.get() is batcher
        assert active_target is None
