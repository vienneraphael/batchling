"""Lifecycle event constants, payload typing, and parsing helpers."""

from __future__ import annotations

import typing as t
from enum import StrEnum


class BatcherEventType(StrEnum):
    """Supported lifecycle event types emitted by ``Batcher``."""

    CACHE_HIT_ROUTED = "cache_hit_routed"
    REQUEST_QUEUED = "request_queued"
    WINDOW_TIMER_ERROR = "window_timer_error"
    BATCH_SUBMITTING = "batch_submitting"
    BATCH_PROCESSING = "batch_processing"
    BATCH_TERMINAL = "batch_terminal"
    BATCH_FAILED = "batch_failed"
    BATCH_POLLED = "batch_polled"
    MISSING_RESULTS = "missing_results"
    FINAL_FLUSH_SUBMITTING = "final_flush_submitting"


class BatcherEventSource(StrEnum):
    """Known lifecycle event sources emitted by ``Batcher`` subsystems."""

    CACHE_DRY_RUN = "cache_dry_run"
    RESUMED_POLL = "resumed_poll"
    WINDOW_TIMER = "window_timer"
    DRY_RUN = "dry_run"
    SUBMIT = "submit"
    POLL_START = "poll_start"
    ACTIVE_POLL = "active_poll"
    RESUMED_RESULTS = "resumed_results"
    RESULTS = "results"
    CLOSE = "close"


class BatcherEvent(t.TypedDict, total=False):
    """
    Lifecycle event emitted by ``Batcher`` for optional observers.

    event_type : str | BatcherEventType
        Event identifier.
    timestamp : float
        Event timestamp in UNIX seconds.
    provider : str
        Provider name.
    endpoint : str
        Request endpoint.
    model : str
        Request model.
    queue_key : tuple[str, str, str]
        Queue identifier.
    batch_id : str
        Provider batch identifier.
    status : str
        Provider batch status.
    request_count : int
        Number of requests in the event scope.
    progress_completed : int
        Completed requests emitted for one poll snapshot.
    progress_percent : float
        Completion percent emitted for one poll snapshot.
    pending_count : int
        Current queue pending size.
    custom_id : str
        Custom request identifier.
    source : str | BatcherEventSource
        Event source subsystem.
    error : str
        Error text.
    missing_count : int
        Number of missing results.
    """

    event_type: str | BatcherEventType
    timestamp: float
    provider: str
    endpoint: str
    model: str
    queue_key: tuple[str, str, str]
    batch_id: str
    status: str
    request_count: int
    progress_completed: int
    progress_percent: float
    pending_count: int
    custom_id: str
    source: str | BatcherEventSource
    error: str
    missing_count: int


def parse_event_type(*, event: BatcherEvent) -> BatcherEventType | None:
    """
    Normalize one lifecycle event type value to a typed enum.

    Parameters
    ----------
    event : BatcherEvent
        Lifecycle event payload.

    Returns
    -------
    BatcherEventType | None
        Parsed lifecycle event type, or ``None`` when missing/unknown.
    """
    raw_event_type = event.get("event_type")
    if isinstance(raw_event_type, BatcherEventType):
        return raw_event_type
    if not isinstance(raw_event_type, str):
        return None
    try:
        return BatcherEventType(raw_event_type)
    except ValueError:
        return None


def parse_event_source(*, event: BatcherEvent) -> BatcherEventSource | None:
    """
    Normalize one lifecycle event source value to a typed enum.

    Parameters
    ----------
    event : BatcherEvent
        Lifecycle event payload.

    Returns
    -------
    BatcherEventSource | None
        Parsed lifecycle event source, or ``None`` when missing/unknown.
    """
    raw_source = event.get("source")
    if isinstance(raw_source, BatcherEventSource):
        return raw_source
    if not isinstance(raw_source, str):
        return None
    try:
        return BatcherEventSource(raw_source)
    except ValueError:
        return None


BatcherEventListener = t.Callable[[BatcherEvent], None]
