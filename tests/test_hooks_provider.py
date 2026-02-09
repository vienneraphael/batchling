"""Tests for hook/batcher/provider integration."""

from unittest.mock import AsyncMock

import httpx
import pytest

import batchling.batching.hooks as hooks_module
from batchling.batching.core import Batcher
from batchling.batching.hooks import active_batcher, install_hooks
from tests.mocks.batching import make_openai_batch_transport


@pytest.mark.asyncio
async def test_hook_routes_openai_url_to_batcher(reset_hooks, reset_context):
    """
    Ensure OpenAI URLs are routed to the active batcher.

    Parameters
    ----------
    reset_hooks : None
        Fixture to reset hook state.
    reset_context : None
        Fixture to reset context variables.
    """
    install_hooks()

    mocked_original = AsyncMock(return_value=httpx.Response(status_code=204))
    hooks_module._original_httpx_async_send = mocked_original

    batcher = Batcher(batch_size=1, batch_window_seconds=1.0)
    transport = make_openai_batch_transport()
    batcher._client_factory = lambda: httpx.AsyncClient(transport=transport)
    batcher._poll_interval_seconds = 0.01
    token = active_batcher.set(batcher)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url="https://api.openai.com/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "hi"}]},
            )
    finally:
        active_batcher.reset(token)
        await batcher.close()

    assert response.status_code == 200
    mocked_original.assert_not_awaited()


@pytest.mark.asyncio
async def test_hook_falls_back_for_unsupported_url(reset_hooks, reset_context):
    """
    Ensure unsupported URLs fall back to the original client.

    Parameters
    ----------
    reset_hooks : None
        Fixture to reset hook state.
    reset_context : None
        Fixture to reset context variables.
    """
    install_hooks()

    mocked_original = AsyncMock(return_value=httpx.Response(status_code=204))
    hooks_module._original_httpx_async_send = mocked_original

    batcher = Batcher(batch_size=1, batch_window_seconds=1.0)
    token = active_batcher.set(batcher)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url="https://example.com/health")
    finally:
        active_batcher.reset(token)
        await batcher.close()

    assert response.status_code == 204
    assert mocked_original.await_count == 1
