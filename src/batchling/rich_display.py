"""Rich live display for batch lifecycle visibility."""

from __future__ import annotations

import os
import sys
import time
import typing as t
from collections import deque
from dataclasses import dataclass

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from batchling.core import BatcherEvent, QueueKey

LiveDisplayMode = t.Literal["auto", "on", "off"]


@dataclass
class _QueueActivity:
    """In-memory queue activity snapshot for rendering."""

    pending_count: int = 0
    active_batches: int = 0
    submitted_batches: int = 0
    last_status: str = "-"
    last_batch_id: str = "-"


class BatcherRichDisplay:
    """
    Render queue and lifecycle activity through a Rich ``Live`` panel.

    Parameters
    ----------
    max_events : int, optional
        Maximum number of lifecycle events kept in the rolling feed.
    refresh_per_second : float, optional
        Refresh rate for Rich live updates.
    console : Console | None, optional
        Rich console to render to. Defaults to ``Console(stderr=True)``.
    """

    def __init__(
        self,
        *,
        max_events: int = 20,
        refresh_per_second: float = 8.0,
        console: Console | None = None,
    ) -> None:
        self._console = console or Console(stderr=True)
        self._max_events = max_events
        self._refresh_per_second = refresh_per_second
        self._events: deque[BatcherEvent] = deque(maxlen=max_events)
        self._queues: dict[QueueKey, _QueueActivity] = {}
        self._live: Live | None = None

    def start(self) -> None:
        """Start the live panel if not already running."""
        if self._live is not None:
            return
        self._live = Live(
            renderable=self._render(),
            console=self._console,
            refresh_per_second=self._refresh_per_second,
            transient=False,
        )
        self._live.start(refresh=True)

    def stop(self) -> None:
        """Stop the live panel if running."""
        if self._live is None:
            return
        self._live.stop()
        self._live = None

    def on_event(self, event: BatcherEvent) -> None:
        """
        Consume one batch lifecycle event and refresh the panel.

        Parameters
        ----------
        event : BatcherEvent
            Lifecycle event emitted by ``Batcher``.
        """
        event_type = str(object=event.get("event_type", "unknown"))
        queue_key = self._resolve_queue_key(event=event)

        if queue_key is not None:
            queue_activity = self._queues.setdefault(queue_key, _QueueActivity())

            if event_type == "request_queued":
                queue_activity.pending_count = int(
                    event.get("pending_count", queue_activity.pending_count)
                )
            elif event_type in {"batch_submitting", "final_flush_submitting"}:
                queue_activity.pending_count = 0
                queue_activity.submitted_batches += 1
            elif event_type == "batch_processing":
                source = str(object=event.get("source", ""))
                if source in {"dry_run", "poll_start"}:
                    queue_activity.active_batches += 1
            elif event_type in {"batch_terminal", "batch_failed"}:
                queue_activity.active_batches = max(0, queue_activity.active_batches - 1)

            event_status = event.get("status")
            if event_status is not None:
                queue_activity.last_status = str(object=event_status)
            event_batch_id = event.get("batch_id")
            if event_batch_id is not None:
                queue_activity.last_batch_id = str(object=event_batch_id)

        self._events.append(event)
        if self._live is not None:
            self._live.update(renderable=self._render(), refresh=True)

    def _resolve_queue_key(self, *, event: BatcherEvent) -> QueueKey | None:
        """
        Resolve queue key from event payload.

        Parameters
        ----------
        event : BatcherEvent
            Event payload.

        Returns
        -------
        QueueKey | None
            Queue key when available.
        """
        raw_queue_key = event.get("queue_key")
        if isinstance(raw_queue_key, tuple) and len(raw_queue_key) == 3:
            provider, endpoint, model = raw_queue_key
            return str(provider), str(endpoint), str(model)

        provider = event.get("provider")
        endpoint = event.get("endpoint")
        model = event.get("model")
        if provider is None or endpoint is None or model is None:
            return None

        return str(provider), str(endpoint), str(model)

    def _render(self) -> Panel:
        """Build the current Rich panel renderable."""
        queue_table = self._build_queue_table()
        event_table = self._build_event_table()
        return Panel(
            renderable=Group(queue_table, event_table),
            title="batchling live activity",
            border_style="cyan",
        )

    def _build_queue_table(self) -> Table:
        """Build queue activity table."""
        table = Table(title="Queues", expand=True)
        table.add_column(header="Provider", style="bold")
        table.add_column(header="Endpoint")
        table.add_column(header="Model")
        table.add_column(header="Pending", justify="right")
        table.add_column(header="Active", justify="right")
        table.add_column(header="Submitted", justify="right")
        table.add_column(header="Last Status")
        table.add_column(header="Batch ID")

        if not self._queues:
            table.add_row("-", "-", "-", "0", "0", "0", "-", "-")
            return table

        for queue_key in sorted(self._queues.keys()):
            provider, endpoint, model = queue_key
            queue_activity = self._queues[queue_key]
            table.add_row(
                provider,
                endpoint,
                model,
                str(queue_activity.pending_count),
                str(queue_activity.active_batches),
                str(queue_activity.submitted_batches),
                queue_activity.last_status,
                queue_activity.last_batch_id,
            )
        return table

    def _build_event_table(self) -> Table:
        """Build rolling lifecycle event feed."""
        table = Table(title=f"Recent Events (max {self._max_events})", expand=True)
        table.add_column(header="Time", width=8)
        table.add_column(header="Event")
        table.add_column(header="Details")

        if not self._events:
            table.add_row("-", "-", "No lifecycle events yet")
            return table

        for event in reversed(self._events):
            event_timestamp = float(event.get("timestamp", time.time()))
            event_time = time.strftime("%H:%M:%S", time.localtime(event_timestamp))
            event_type = str(object=event.get("event_type", "unknown"))
            details = self._format_event_details(event=event)
            table.add_row(event_time, event_type, details)

        return table

    def _format_event_details(self, *, event: BatcherEvent) -> Text:
        """
        Build compact details text for one event row.

        Parameters
        ----------
        event : BatcherEvent
            Event payload.

        Returns
        -------
        Text
            Formatted details.
        """
        details: list[str] = []
        provider = event.get("provider")
        endpoint = event.get("endpoint")
        model = event.get("model")
        batch_id = event.get("batch_id")
        status = event.get("status")
        pending_count = event.get("pending_count")
        request_count = event.get("request_count")
        error = event.get("error")

        if provider is not None:
            details.append(f"provider={provider}")
        if endpoint is not None:
            details.append(f"endpoint={endpoint}")
        if model is not None:
            details.append(f"model={model}")
        if pending_count is not None:
            details.append(f"pending={pending_count}")
        if request_count is not None:
            details.append(f"requests={request_count}")
        if batch_id is not None:
            details.append(f"batch_id={batch_id}")
        if status is not None:
            details.append(f"status={status}")
        if error is not None:
            details.append(f"error={error}")

        return Text(" ".join(details) if details else "-")


def should_enable_live_display(*, mode: LiveDisplayMode) -> bool:
    """
    Resolve if the Rich live panel should be enabled.

    Parameters
    ----------
    mode : LiveDisplayMode
        Desired display mode.

    Returns
    -------
    bool
        ``True`` when the live panel should run.
    """
    if mode == "on":
        return True
    if mode == "off":
        return False

    stderr_stream = sys.stderr
    is_tty = bool(getattr(stderr_stream, "isatty", lambda: False)())
    terminal_name = str(object=os.environ.get("TERM", "")).lower()
    is_dumb_terminal = terminal_name in {"", "dumb"}
    is_ci = bool(os.environ.get("CI"))

    return is_tty and not is_dumb_terminal and not is_ci
