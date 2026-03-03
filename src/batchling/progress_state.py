"""Shared progress-state tracking for live display and fallback logging."""

from __future__ import annotations

import time
import typing as t
from dataclasses import dataclass

from batchling.core import BatcherEvent


@dataclass
class _TrackedBatch:
    """In-memory batch state used for aggregate progress computations."""

    batch_id: str
    provider: str = "-"
    endpoint: str = "-"
    model: str = "-"
    size: int = 0
    completed: bool = False
    terminal: bool = False


@dataclass
class _DryRunQueueSummary:
    """Aggregated dry-run counters per queue key."""

    expected_requests: int = 0
    expected_batches: int = 0


class BatchProgressState:
    """
    Track batch lifecycle state and compute shared aggregate metrics.

    Parameters
    ----------
    now_fn : typing.Callable[[], float] | None, optional
        Clock function used for elapsed-time calculations.
    """

    def __init__(
        self,
        *,
        now_fn: t.Callable[[], float] | None = None,
    ) -> None:
        self._now_fn = now_fn or time.time
        self._batches: dict[str, _TrackedBatch] = {}
        self._cached_samples = 0
        self._first_batch_created_at: float | None = None

    def on_event(self, *, event: BatcherEvent) -> None:
        """
        Update tracked state from one lifecycle event.

        Parameters
        ----------
        event : BatcherEvent
            Lifecycle event emitted by ``Batcher``.
        """
        event_type = str(object=event.get("event_type", "unknown"))
        source = str(object=event.get("source", ""))
        batch_id = event.get("batch_id")

        if batch_id is None:
            return

        batch = self._get_or_create_batch(batch_id=str(object=batch_id))
        self._update_batch_identity(batch=batch, event=event)

        if event_type == "batch_processing":
            request_count = event.get("request_count")
            if isinstance(request_count, int):
                batch.size = max(batch.size, request_count)
            batch.terminal = False
            return

        if event_type == "batch_polled":
            batch.terminal = False
            return

        if event_type == "batch_terminal":
            status = str(object=event.get("status", "completed"))
            batch.completed = self._status_counts_as_completed(status=status)
            batch.terminal = True
            return

        if event_type == "batch_failed":
            batch.completed = False
            batch.terminal = True
            return

        if event_type == "cache_hit_routed" and source == "resumed_poll":
            batch.size += 1
            self._cached_samples += 1
            batch.terminal = False

    def compute_progress(self) -> tuple[int, int, float]:
        """
        Compute aggregate sample progress from tracked batches.

        Returns
        -------
        tuple[int, int, float]
            ``(completed_samples, total_samples, percent)``.
        """
        total_samples = sum(batch.size for batch in self._batches.values())
        completed_samples = sum(batch.size for batch in self._batches.values() if batch.completed)
        if total_samples <= 0:
            return 0, 0, 0.0
        percent = (completed_samples / total_samples) * 100.0
        return completed_samples, total_samples, percent

    def compute_request_metrics(self) -> tuple[int, int, int, int]:
        """
        Compute aggregate request counters from tracked batches.

        Returns
        -------
        tuple[int, int, int, int]
            ``(total_samples, cached_samples, completed_samples, in_progress_samples)``.
        """
        total_samples = sum(batch.size for batch in self._batches.values())
        completed_samples = sum(batch.size for batch in self._batches.values() if batch.completed)
        in_progress_samples = sum(
            batch.size for batch in self._batches.values() if not batch.terminal
        )
        return total_samples, self._cached_samples, completed_samples, in_progress_samples

    def compute_queue_batch_counts(self) -> list[tuple[str, str, str, int, int]]:
        """
        Aggregate queue-level running and terminal batch counts.

        Returns
        -------
        list[tuple[str, str, str, int, int]]
            Sorted rows as ``(provider, endpoint, model, running, completed)``.
        """
        counts_by_queue: dict[tuple[str, str, str], list[int]] = {}
        for batch in self._batches.values():
            queue_key = (batch.provider, batch.endpoint, batch.model)
            counters = counts_by_queue.setdefault(queue_key, [0, 0])
            if batch.terminal:
                counters[1] += 1
            else:
                counters[0] += 1

        rows = [
            (provider, endpoint, model, counters[0], counters[1])
            for (provider, endpoint, model), counters in counts_by_queue.items()
        ]
        return sorted(rows, key=lambda row: (row[0], row[1], row[2]))

    def compute_elapsed_seconds(self) -> int:
        """
        Compute elapsed seconds since first tracked batch in this context.

        Returns
        -------
        int
            Elapsed seconds.
        """
        if self._first_batch_created_at is None:
            return 0
        return max(0, int(self._now_fn() - self._first_batch_created_at))

    def _get_or_create_batch(self, *, batch_id: str) -> _TrackedBatch:
        """
        Get or create one tracked batch record.

        Parameters
        ----------
        batch_id : str
            Provider batch identifier.

        Returns
        -------
        _TrackedBatch
            Mutable tracked batch.
        """
        batch = self._batches.get(batch_id)
        if batch is None:
            batch = _TrackedBatch(batch_id=batch_id)
            self._batches[batch_id] = batch
            if self._first_batch_created_at is None:
                self._first_batch_created_at = self._now_fn()
        return batch

    @staticmethod
    def _update_batch_identity(*, batch: _TrackedBatch, event: BatcherEvent) -> None:
        """
        Update batch metadata from lifecycle event payload.

        Parameters
        ----------
        batch : _TrackedBatch
            Mutable tracked batch.
        event : BatcherEvent
            Lifecycle event payload.
        """
        provider = event.get("provider")
        endpoint = event.get("endpoint")
        model = event.get("model")
        if provider is not None:
            batch.provider = str(object=provider)
        if endpoint is not None:
            batch.endpoint = str(object=endpoint)
        if model is not None:
            batch.model = str(object=model)

    @staticmethod
    def _status_counts_as_completed(*, status: str) -> bool:
        """
        Determine whether a terminal status counts as completed samples.

        Parameters
        ----------
        status : str
            Terminal provider status.

        Returns
        -------
        bool
            ``True`` when terminal state should contribute to completed samples.
        """
        lowered_status = status.lower()
        negative_markers = ("fail", "error", "cancel", "expired", "timeout")
        if any(marker in lowered_status for marker in negative_markers):
            return False
        return True


class DryRunSummaryState:
    """
    Aggregate dry-run request and batch estimates from lifecycle events.

    Notes
    -----
    This state tracks only dry-run relevant counters and is intended to feed
    a static summary rendered at context teardown.
    """

    def __init__(self) -> None:
        self._would_batch_requests_total = 0
        self._would_cache_requests_total = 0
        self._queue_counts: dict[tuple[str, str, str], _DryRunQueueSummary] = {}

    def on_event(self, *, event: BatcherEvent) -> None:
        """
        Update summary counters using one lifecycle event.

        Parameters
        ----------
        event : BatcherEvent
            Lifecycle event emitted by ``Batcher``.
        """
        event_type = str(object=event.get("event_type", "unknown"))
        source = str(object=event.get("source", ""))

        if event_type == "request_queued":
            queue_key = self._extract_queue_key(event=event)
            if queue_key is None:
                return
            self._would_batch_requests_total += 1
            queue_summary = self._queue_counts.setdefault(queue_key, _DryRunQueueSummary())
            queue_summary.expected_requests += 1
            return

        if event_type == "batch_processing" and source == "dry_run":
            queue_key = self._extract_queue_key(event=event)
            if queue_key is None:
                return
            queue_summary = self._queue_counts.setdefault(queue_key, _DryRunQueueSummary())
            queue_summary.expected_batches += 1
            return

        if event_type == "cache_hit_routed" and source == "cache_dry_run":
            self._would_cache_requests_total += 1

    @property
    def would_batch_requests_total(self) -> int:
        """
        Total number of requests that would have been batched.

        Returns
        -------
        int
            Global count of queued requests.
        """
        return self._would_batch_requests_total

    @property
    def would_cache_requests_total(self) -> int:
        """
        Total number of dry-run cache-hit requests.

        Returns
        -------
        int
            Global dry-run cache-hit count.
        """
        return self._would_cache_requests_total

    def compute_queue_rows(self) -> list[tuple[str, str, str, int, int]]:
        """
        Return sorted per-queue dry-run summary rows.

        Returns
        -------
        list[tuple[str, str, str, int, int]]
            Rows formatted as
            ``(provider, endpoint, model, expected_requests, expected_batches)``.
        """
        rows = [
            (
                provider,
                endpoint,
                model,
                queue_summary.expected_requests,
                queue_summary.expected_batches,
            )
            for (provider, endpoint, model), queue_summary in self._queue_counts.items()
        ]
        return sorted(rows, key=lambda row: (row[0], row[1], row[2]))

    @staticmethod
    def _extract_queue_key(*, event: BatcherEvent) -> tuple[str, str, str] | None:
        """
        Extract queue key from lifecycle event payload.

        Parameters
        ----------
        event : BatcherEvent
            Lifecycle event payload.

        Returns
        -------
        tuple[str, str, str] | None
            Queue key when available.
        """
        queue_key = event.get("queue_key")
        if (
            isinstance(queue_key, tuple)
            and len(queue_key) == 3
            and all(isinstance(part, str) for part in queue_key)
        ):
            return queue_key

        provider = event.get("provider")
        endpoint = event.get("endpoint")
        model = event.get("model")
        if provider is None or endpoint is None or model is None:
            return None
        return (
            str(object=provider),
            str(object=endpoint),
            str(object=model),
        )
