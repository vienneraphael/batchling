"""Rich live display for batch lifecycle visibility."""

from __future__ import annotations

import os
import sys
import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text

from batchling.lifecycle_events import BatcherEvent
from batchling.progress_state import BatchProgressState, DryRunSummaryState


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
        refresh_per_second: float = 1.0,
        console: Console | None = None,
    ) -> None:
        self._console = console or Console(stderr=True)
        self._refresh_per_second = refresh_per_second
        self._progress_state = BatchProgressState(now_fn=time.time)
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
        self._progress_state.on_event(event=event)
        self.refresh()

    def refresh(self) -> None:
        """Force one live-panel refresh when running."""
        if self._live is None:
            return
        self._live.update(renderable=self._render(), refresh=True)

    def _compute_progress(self) -> tuple[int, int, float]:
        """
        Compute aggregate context progress from tracked batches.

        Returns
        -------
        tuple[int, int, float]
            ``(completed_samples, total_samples, percent)``.
        """
        return self._progress_state.compute_progress()

    def _compute_request_metrics(self) -> tuple[int, int, int, int]:
        """
        Compute aggregate request counters shown under the progress bar.

        Returns
        -------
        tuple[int, int, int, int]
            ``(total_samples, cached_samples, completed_samples, in_progress_samples)``.
        """
        return self._progress_state.compute_request_metrics()

    def _compute_elapsed_seconds(self) -> int:
        """
        Compute elapsed seconds since first batch creation in this context.

        Returns
        -------
        int
            Elapsed seconds.
        """
        return self._progress_state.compute_elapsed_seconds()

    @staticmethod
    def _format_elapsed(*, elapsed_seconds: int) -> str:
        """
        Format elapsed seconds as ``HH:MM:SS``.

        Parameters
        ----------
        elapsed_seconds : int
            Elapsed seconds.

        Returns
        -------
        str
            Formatted duration.
        """
        hours = elapsed_seconds // 3600
        minutes = (elapsed_seconds % 3600) // 60
        seconds = elapsed_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _render(self) -> Panel:
        """Build the current Rich panel renderable."""
        progress_bar = self._build_progress_bar()
        requests_line = self._build_requests_line()
        queue_summary_table = self._build_queue_summary_table()
        return Panel(
            renderable=Group(progress_bar, requests_line, queue_summary_table),
            title="batchling context progress",
            border_style="cyan",
        )

    def _build_progress_bar(self) -> Progress:
        """Build aggregate context progress as a Rich progress bar."""
        completed_samples, total_samples, _ = self._compute_progress()
        elapsed_seconds = self._compute_elapsed_seconds()
        elapsed_label = self._format_elapsed(elapsed_seconds=elapsed_seconds)
        sample_width = max(1, len(str(object=total_samples)))

        progress = Progress(
            BarColumn(bar_width=None),
            TextColumn(
                text_format=(
                    f"[bold green]{{task.fields[completed_samples]:>{sample_width}}}[/bold green]/"
                    f"[bold cyan]{{task.fields[total_samples]:>{sample_width}}}[/bold cyan] "
                    "([bold green]{task.percentage:.1f}%[/bold green])"
                )
            ),
            TextColumn(text_format=f"Time Elapsed: [bold magenta]{elapsed_label}[/bold magenta]"),
            expand=True,
        )
        display_total = max(total_samples, 1)
        _ = progress.add_task(
            description="samples",
            total=display_total,
            completed=min(completed_samples, display_total),
            completed_samples=completed_samples,
            total_samples=total_samples,
        )
        return progress

    def _build_requests_line(self) -> Text:
        """
        Build one-line request metrics shown under the progress bar.

        Returns
        -------
        Text
            Styled metrics line.
        """
        total_samples, cached_samples, completed_samples, in_progress_samples = (
            self._compute_request_metrics()
        )
        line = Text()
        line.append(text="Requests", style="bold white")
        line.append(text=": ", style="white")
        line.append(text="Total", style="grey70")
        line.append(text=": ", style="grey70")
        line.append(text=str(object=total_samples), style="bold cyan")
        line.append(text="  -  ", style="grey70")
        line.append(text="Cached", style="grey70")
        line.append(text=": ", style="grey70")
        line.append(text=str(object=cached_samples), style="bold magenta")
        line.append(text="  -  ", style="grey70")
        line.append(text="Completed", style="grey70")
        line.append(text=": ", style="grey70")
        line.append(text=str(object=completed_samples), style="bold green")
        line.append(text="  -  ", style="grey70")
        line.append(text="In Progress", style="grey70")
        line.append(text=": ", style="grey70")
        line.append(text=str(object=in_progress_samples), style="bold yellow")
        return line

    def _compute_queue_batch_counts(self) -> list[tuple[str, str, str, int, int]]:
        """
        Aggregate queue-level running and terminal batch counts.

        Returns
        -------
        list[tuple[str, str, str, int, int]]
            Sorted rows as ``(provider, endpoint, model, running, completed)``.
        """
        return self._progress_state.compute_queue_batch_counts()

    def _build_queue_summary_table(self) -> Table:
        """
        Build queue-level table with per-queue progress summary.

        Returns
        -------
        Table
            Queue summary table.
        """
        queue_rows = self._compute_queue_batch_counts()
        table = Table(expand=False)
        table.add_column(
            header="provider",
            style="bold blue",
            width=12,
            no_wrap=True,
            overflow="ellipsis",
        )
        table.add_column(
            header="endpoint",
            width=34,
            no_wrap=True,
            overflow="ellipsis",
        )
        table.add_column(
            header="model",
            style="bold magenta",
            width=28,
            no_wrap=True,
            overflow="ellipsis",
        )
        table.add_column(
            header="progress",
            justify="right",
            width=16,
            no_wrap=True,
            overflow="ellipsis",
        )

        if not queue_rows:
            table.add_row("-", "-", "-", self._format_queue_progress(running=0, completed=0))
            return table

        for provider, endpoint, model, running, completed in queue_rows:
            table.add_row(
                provider,
                endpoint,
                model,
                self._format_queue_progress(
                    running=running,
                    completed=completed,
                ),
            )
        return table

    @staticmethod
    def _format_queue_progress(*, running: int, completed: int) -> Text:
        """
        Format one queue progress cell as ``completed/total (percent)``.

        Parameters
        ----------
        running : int
            Number of non-terminal batches.
        completed : int
            Number of terminal batches.

        Returns
        -------
        Text
            Formatted queue progress.
        """
        total = running + completed
        if total <= 0:
            percent = 0.0
        else:
            percent = (completed / total) * 100.0
        count_width = max(1, len(str(object=total)))
        progress = Text()
        progress.append(text=f"{completed:>{count_width}}", style="bold green")
        progress.append(text="/", style="white")
        progress.append(text=f"{total:>{count_width}}", style="bold cyan")
        progress.append(text=" (", style="white")
        progress.append(text=f"{percent:.1f}%", style="bold green")
        progress.append(text=")", style="white")
        return progress


class DryRunSummaryDisplay:
    """
    Render a static Rich report for dry-run planning totals.

    Parameters
    ----------
    console : Console | None, optional
        Rich console to render to. Defaults to ``Console(stderr=True)``.
    """

    def __init__(
        self,
        *,
        console: Console | None = None,
    ) -> None:
        self._console = console or Console(stderr=True)
        self._summary_state = DryRunSummaryState()

    def on_event(self, event: BatcherEvent) -> None:
        """
        Consume one lifecycle event for dry-run summary aggregation.

        Parameters
        ----------
        event : BatcherEvent
            Lifecycle event emitted by ``Batcher``.
        """
        self._summary_state.on_event(event=event)

    def print_summary(self) -> None:
        """Print the static dry-run report panel."""
        self._console.print(self._render())

    def _render(self) -> Panel:
        """Build the static dry-run summary panel."""
        return Panel(
            renderable=Group(
                self._build_totals_line(),
                self._build_queue_summary_table(),
            ),
            title="batchling dry run summary",
            border_style="yellow",
        )

    def _build_totals_line(self) -> Text:
        """
        Build top-level totals line for the dry-run report.

        Returns
        -------
        Text
            Styled totals text.
        """
        line = Text()
        line.append(text="Batchable Requests", style="grey70")
        line.append(text=": ", style="grey70")
        line.append(
            text=str(object=self._summary_state.would_batch_requests_total),
            style="bold cyan",
        )
        line.append(text="  -  ", style="grey70")
        line.append(text="Cache Hit Requests", style="grey70")
        line.append(text=": ", style="grey70")
        line.append(
            text=str(object=self._summary_state.would_cache_requests_total),
            style="bold magenta",
        )
        return line

    def _build_queue_summary_table(self) -> Table:
        """
        Build queue-level dry-run estimate table.

        Returns
        -------
        Table
            Queue estimate table.
        """
        queue_rows = self._summary_state.compute_queue_rows()
        table = Table(expand=False)
        table.add_column(
            header="provider",
            style="bold blue",
            width=12,
            no_wrap=True,
            overflow="ellipsis",
        )
        table.add_column(
            header="endpoint",
            width=34,
            no_wrap=True,
            overflow="ellipsis",
        )
        table.add_column(
            header="model",
            style="bold magenta",
            width=28,
            no_wrap=True,
            overflow="ellipsis",
        )
        table.add_column(
            header="expected requests",
            justify="right",
            width=17,
            no_wrap=True,
            overflow="ellipsis",
        )
        table.add_column(
            header="expected batches",
            justify="right",
            width=16,
            no_wrap=True,
            overflow="ellipsis",
        )

        if not queue_rows:
            table.add_row("-", "-", "-", "0", "0")
            return table

        for provider, endpoint, model, expected_requests, expected_batches in queue_rows:
            table.add_row(
                provider,
                endpoint,
                model,
                str(object=expected_requests),
                str(object=expected_batches),
            )
        return table


def should_enable_live_display(*, enabled: bool) -> bool:
    """
    Resolve if the Rich live panel should be enabled.

    Parameters
    ----------
    enabled : bool
        Requested live display toggle.

    Returns
    -------
    bool
        ``True`` when the live panel should run.
    """
    if not enabled:
        return False

    stderr_stream = sys.stderr
    is_tty = bool(getattr(stderr_stream, "isatty", lambda: False)())
    terminal_name = str(object=os.environ.get("TERM", "")).lower()
    is_dumb_terminal = terminal_name in {"", "dumb"}
    is_ci = bool(os.environ.get("CI"))

    return is_tty and not is_dumb_terminal and not is_ci
