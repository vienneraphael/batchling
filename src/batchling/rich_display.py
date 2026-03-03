"""Rich live display for batch lifecycle visibility."""

from __future__ import annotations

import os
import sys
import time
import typing as t
from dataclasses import dataclass

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from batchling.core import BatcherEvent

LiveDisplayMode = t.Literal["auto", "on", "off"]


@dataclass
class _BatchActivity:
    """In-memory batch activity snapshot for progress aggregation."""

    batch_id: str
    size: int = 0
    latest_status: str = "submitted"
    completed: bool = False
    updated_at: float = 0.0


class BatcherRichDisplay:
    """
    Render context-level sample progress through a Rich ``Live`` panel.

    Progress is computed from tracked sent batches as:
    ``sum(size of completed batches) / sum(size of all tracked batches)``.

    Parameters
    ----------
    refresh_per_second : float, optional
        Refresh rate for Rich live updates.
    console : Console | None, optional
        Rich console to render to. Defaults to ``Console(stderr=True)``.
    """

    def __init__(
        self,
        *,
        refresh_per_second: float = 8.0,
        console: Console | None = None,
    ) -> None:
        self._console = console or Console(stderr=True)
        self._refresh_per_second = refresh_per_second
        self._batches: dict[str, _BatchActivity] = {}
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
        source = str(object=event.get("source", ""))
        batch_id = event.get("batch_id")

        if batch_id is not None and event_type == "batch_processing":
            batch = self._get_or_create_batch(batch_id=str(object=batch_id))
            request_count = event.get("request_count")
            if isinstance(request_count, int):
                batch.size = max(batch.size, request_count)
            batch.latest_status = "simulated" if source == "dry_run" else "submitted"
        elif batch_id is not None and event_type == "batch_polled":
            batch = self._get_or_create_batch(batch_id=str(object=batch_id))
            status = event.get("status")
            if status is not None:
                batch.latest_status = str(object=status)
        elif batch_id is not None and event_type == "batch_terminal":
            batch = self._get_or_create_batch(batch_id=str(object=batch_id))
            status = str(object=event.get("status", "completed"))
            batch.latest_status = status
            batch.completed = self._status_counts_as_completed(status=status)
        elif batch_id is not None and event_type == "batch_failed":
            batch = self._get_or_create_batch(batch_id=str(object=batch_id))
            batch.latest_status = "failed"
            batch.completed = False
        elif batch_id is not None and event_type == "cache_hit_routed" and source == "resumed_poll":
            batch = self._get_or_create_batch(batch_id=str(object=batch_id))
            batch.size += 1
            if batch.latest_status == "submitted":
                batch.latest_status = "resumed"

        if self._live is not None:
            self._live.update(renderable=self._render(), refresh=True)

    def _get_or_create_batch(self, *, batch_id: str) -> _BatchActivity:
        """
        Fetch or create batch display state.

        Parameters
        ----------
        batch_id : str
            Provider batch identifier.

        Returns
        -------
        _BatchActivity
            Batch display state.
        """
        batch = self._batches.get(batch_id)
        if batch is None:
            batch = _BatchActivity(batch_id=batch_id)
            self._batches[batch_id] = batch
        batch.updated_at = time.time()
        return batch

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

    def _compute_progress(self) -> tuple[int, int, float]:
        """
        Compute aggregate context progress from tracked batches.

        Returns
        -------
        tuple[int, int, float]
            ``(completed_samples, total_samples, percent)``.
        """
        total_samples = sum(batch.size for batch in self._batches.values())
        completed_samples = sum(batch.size for batch in self._batches.values() if batch.completed)
        if total_samples <= 0:
            return 0, 0, 0.0
        percent = (completed_samples / total_samples) * 100
        return completed_samples, total_samples, percent

    def _render(self) -> Panel:
        """Build the current Rich panel renderable."""
        table = self._build_progress_table()
        return Panel(
            renderable=table,
            title="batchling context progress",
            border_style="cyan",
        )

    def _build_progress_table(self) -> Table:
        """Build aggregate context progress table."""
        completed_samples, total_samples, percent = self._compute_progress()

        table = Table(title="Overall Progress", expand=True)
        table.add_column(header="Completed Samples", justify="right")
        table.add_column(header="Total Samples", justify="right")
        table.add_column(header="Completion", justify="right")

        table.add_row(
            str(completed_samples),
            str(total_samples),
            f"{percent:.1f}%",
        )
        return table


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
