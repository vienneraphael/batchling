"""
Core engine containing the async batch watching mechanism.
The mechanism acts as a batch queue that collects requests and submits them as batches.
Should support multiple queues for multiple providers/models called in same job.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncio


@dataclass
class _PendingRequest:
    # FIXME: _PendingRequest can use a generic type to match any request from:
    # - http.client.HTTPSConnection.request
    # - aiohttp.ClientSession._request
    # - httpx.AsyncClient.request
    """A request waiting to be batched."""

    custom_id: str
    params: dict[str, Any]
    future: asyncio.Future


@dataclass
class _ActiveBatch:
    """A batch that has been submitted and is being polled."""

    batch_id: str
    output_file_id: str
    error_file_id: str
    requests: dict[str, _PendingRequest]  # custom_id -> request
    created_at: float
    last_offset: int = 0  # Track offset for partial result streaming


class Batcher:
    """
    Manages queues, timers, and the accumulate-submit-poll lifecycle.
    """
    def __init__(self, batch_size=10, batch_window=2.0, ...):
        # ...

    def identifies_provider(self, url: str) -> bool:
        """True if we have a Provider strategy for this URL."""

    async def submit(self, client_type: str, method, url, kwargs) -> Response:
        """
        Main entry point for the Hook.
        1. Transforms request using Provider adapter
        2. Adds to queue
        3. Awaits Future
        4. Returns reconstructed Response
        """

    async def _worker_loop(self):
        """Background task that watches queues."""

    async def close(self):
        """Cleanup resources."""
