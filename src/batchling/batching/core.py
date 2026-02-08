"""
Core engine containing the async batch watching mechanism.
The mechanism acts as a batch queue that collects requests and submits them as batches.
Should support multiple queues for multiple providers/models called in same job.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any

import structlog

from batchling.batching.providers import BaseProvider, get_provider_for_url

log = structlog.get_logger(__name__)


@dataclass
class _PendingRequest:
    # FIXME: _PendingRequest can use a generic type to match any request from:
    # - http.client.HTTPSConnection.request
    # - aiohttp.ClientSession._request
    # - httpx.AsyncClient.request
    """A request waiting to be batched."""

    custom_id: str
    params: dict[str, Any]
    provider: BaseProvider
    future: asyncio.Future[Any]


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

    Collects requests over a time window or until a size threshold, then submits
    them as batches. Batches are sent when either:
    - The batch queue reaches batch_size, OR
    - The batch_window_seconds time elapses

    Usage:
        batcher = Batcher(
            batch_size=100,
            batch_window_seconds=1.0,
        )

        # Submit requests
        result = await batcher.submit(...)
    """

    def __init__(
        self,
        batch_size: int = 10,
        batch_window_seconds: float = 2.0,
    ):
        """
        Initialize Batcher.

        Args:
            batch_size: Submit batch when this many requests are queued
            batch_window_seconds: Submit batch after this many seconds, even if size not reached
        """
        self._batch_size = batch_size
        self._batch_window_seconds = batch_window_seconds

        # Request collection
        self._pending: list[_PendingRequest] = []
        self._pending_lock = asyncio.Lock()
        self._window_task: asyncio.Task[None] | None = None

        # Active batches being tracked
        self._active_batches: list[_ActiveBatch] = []

        log.debug(
            "Initialized Batcher",
            batch_size=batch_size,
            batch_window_seconds=batch_window_seconds,
        )

    async def submit(
        self,
        client_type: str,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: Any = None,
        **kwargs: Any,
    ) -> Any:
        """
        Main entry point for the Hook.
        1. Transforms request using Provider adapter (TODO)
        2. Adds to queue
        3. Awaits Future
        4. Returns reconstructed Response (TODO)

        Args:
            client_type: Type of client (e.g., 'httpx', 'aiohttp')
            method: HTTP method (e.g., 'GET', 'POST')
            url: Request URL
            **kwargs: Additional request parameters

        Returns:
            Response object (to be implemented)
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()

        provider = get_provider_for_url(url)
        if provider is None:
            raise ValueError(f"No provider registered for URL: {url}")

        custom_id = str(uuid.uuid4())

        request = _PendingRequest(
            custom_id=custom_id,
            params={
                "client_type": client_type,
                "method": method,
                "url": url,
                "headers": headers,
                "body": body,
                **kwargs,
            },
            provider=provider,
            future=future,
        )

        async with self._pending_lock:
            self._pending.append(request)
            pending_count = len(self._pending)

            # Start window timer if this is the first request
            if pending_count == 1:
                log.debug(
                    "Starting batch window timer",
                    batch_window_seconds=self._batch_window_seconds,
                )
                self._window_task = asyncio.create_task(
                    self._window_timer(),
                    name="batch_window_timer",
                )

            # Check if we've hit the size threshold
            if pending_count >= self._batch_size:
                log.debug("Batch size reached", batch_size=self._batch_size)
                await self._submit_batch()

        return await future

    async def _window_timer(self) -> None:
        """Timer that triggers batch submission after the window elapses."""
        try:
            await asyncio.sleep(self._batch_window_seconds)
            async with self._pending_lock:
                if self._pending:
                    log.debug("Batch window elapsed, submitting batch")
                    await self._submit_batch()
        except asyncio.CancelledError:
            log.debug("Window timer cancelled")
            raise
        except Exception as e:
            log.error("Window timer error", error=str(e))
            # Fail all pending futures
            async with self._pending_lock:
                for req in self._pending:
                    if not req.future.done():
                        req.future.set_exception(e)
            raise

    async def _submit_batch(self) -> None:
        """Submit all pending requests as a batch."""
        if not self._pending:
            return

        # Cancel the window timer if running (but not if we ARE the window timer)
        current_task = asyncio.current_task()
        if (
            self._window_task
            and not self._window_task.done()
            and self._window_task is not current_task
        ):
            self._window_task.cancel()
        self._window_task = None

        # Take all pending requests
        requests = self._pending
        self._pending = []

        try:
            log.info("Submitting batch", request_count=len(requests))

            # Create a batch ID
            batch_id = str(uuid.uuid4())

            # Track the active batch
            active_batch = _ActiveBatch(
                batch_id=batch_id,
                output_file_id="",  # TODO: Set when batch is submitted
                error_file_id="",  # TODO: Set when batch is submitted
                requests={req.custom_id: req for req in requests},
                created_at=time.time(),
            )
            self._active_batches.append(active_batch)

            # TODO: Actually submit the batch to the provider's batch API
            # For now, we'll simulate by immediately resolving futures
            # This should be replaced with actual batch submission logic
            log.warning(
                "Batch submission not yet implemented - resolving futures immediately",
                batch_id=batch_id,
            )
            for req in requests:
                if not req.future.done():
                    # TODO: Replace with actual response from batch API
                    result_item = {
                        "custom_id": req.custom_id,
                        "error": {
                            "status_code": 400,
                            "message": "Batch submission not yet implemented",
                        },
                    }
                    response = req.provider.from_batch_result(result_item)
                    req.future.set_result(response)

        except Exception as e:
            log.error("Batch submission failed", error=str(e))
            # If batch submission fails, fail all waiting requests
            for req in requests:
                if not req.future.done():
                    req.future.set_exception(e)

    async def _worker_loop(self) -> None:
        """Background task that watches queues."""
        # TODO: Implement worker loop for polling batch status
        # This would poll active batches and resolve futures as results come in
        pass

    async def close(self) -> None:
        """Cleanup resources."""
        # Cancel the window timer if running
        if self._window_task and not self._window_task.done():
            self._window_task.cancel()
            try:
                await self._window_task
            except asyncio.CancelledError:
                pass

        # Submit any remaining pending requests
        async with self._pending_lock:
            if self._pending:
                log.info(
                    "Submitting final batch on close",
                    request_count=len(self._pending),
                )
                await self._submit_batch()

        log.debug("Batcher closed")
