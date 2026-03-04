"""
Context manager returned by ``batchify``.
"""

import asyncio
import logging
import typing as t
import warnings

from batchling.core import Batcher
from batchling.exceptions import DryRunEarlyExit
from batchling.hooks import active_batcher
from batchling.lifecycle_events import BatcherEvent, BatcherEventType, parse_event_type
from batchling.logging import log_info
from batchling.progress_state import BatchProgressState
from batchling.rich_display import (
    BatcherRichDisplay,
    DryRunSummaryDisplay,
    should_enable_live_display,
)

log = logging.getLogger(name=__name__)


class _PollingProgressLogger:
    """INFO logger fallback used when Rich live display auto-disables."""

    def __init__(self) -> None:
        self._progress_state = BatchProgressState()

    def on_event(self, event: BatcherEvent) -> None:
        """
        Consume one lifecycle event and log progress on poll events.

        Parameters
        ----------
        event : BatcherEvent
            Lifecycle event emitted by ``Batcher``.
        """
        self._progress_state.on_event(event=event)

        event_type = parse_event_type(event=event)
        if event_type is not BatcherEventType.BATCH_POLLED:
            return

        completed_samples, total_samples, percent = self._progress_state.compute_progress()
        _, _, _, in_progress_samples = self._progress_state.compute_request_metrics()
        log_info(
            logger=log,
            event="Live display fallback progress",
            batch_id=event.get("batch_id"),
            status=event.get("status"),
            completed_samples=completed_samples,
            total_samples=total_samples,
            percent=f"{percent:.1f}",
            in_progress_samples=in_progress_samples,
        )


class BatchingContext:
    """
    Context manager that activates a batcher for a scoped block.

    Parameters
    ----------
    batcher : Batcher
        Batcher instance used for the scope of the context manager.
    live_display : bool, optional
        Whether to enable auto live display behavior for the context.
    """

    def __init__(
        self,
        *,
        batcher: "Batcher",
        live_display: bool = True,
    ) -> None:
        """
        Initialize the context manager.

        Parameters
        ----------
        batcher : Batcher
            Batcher instance used for the scope of the context manager.
        live_display : bool, optional
            Whether to enable auto live display behavior for the context.
        """
        self._self_batcher = batcher
        self._self_live_display_enabled = live_display
        self._self_live_display: BatcherRichDisplay | None = None
        self._self_live_display_heartbeat_task: asyncio.Task[None] | None = None
        self._self_polling_progress_logger: _PollingProgressLogger | None = None
        self._self_dry_run_summary_display: DryRunSummaryDisplay | None = None
        self._self_dry_run_summary_printed = False
        self._self_context_token: t.Any | None = None

    def _start_dry_run_summary_listener(self) -> None:
        """
        Start dry-run summary listener for static teardown reporting.

        Notes
        -----
        Listener errors are downgraded to warnings to avoid breaking batching.
        """
        if not self._self_batcher._dry_run:
            return
        if self._self_dry_run_summary_display is not None:
            return
        try:
            display = DryRunSummaryDisplay()
            self._self_batcher._add_event_listener(listener=display.on_event)
            self._self_dry_run_summary_display = display
        except Exception as error:
            warnings.warn(
                message=f"Failed to start batchling dry-run summary listener: {error}",
                category=UserWarning,
                stacklevel=2,
            )

    def _stop_dry_run_summary_listener(self) -> None:
        """
        Stop and unregister the dry-run summary listener.

        Notes
        -----
        Listener shutdown errors are downgraded to warnings.
        """
        display = self._self_dry_run_summary_display
        if display is None:
            return
        self._self_dry_run_summary_display = None
        try:
            self._self_batcher._remove_event_listener(listener=display.on_event)
        except Exception as error:
            warnings.warn(
                message=f"Failed to stop batchling dry-run summary listener: {error}",
                category=UserWarning,
                stacklevel=2,
            )

    def _print_dry_run_summary_once(self) -> None:
        """
        Print static dry-run summary report exactly once.

        Notes
        -----
        Reporting errors are downgraded to warnings.
        """
        display = self._self_dry_run_summary_display
        if display is None:
            return
        if self._self_dry_run_summary_printed:
            return
        try:
            display.print_summary()
            self._self_dry_run_summary_printed = True
        except Exception as error:
            warnings.warn(
                message=f"Failed to print batchling dry-run summary: {error}",
                category=UserWarning,
                stacklevel=2,
            )

    def _finalize_context_displays(self) -> None:
        """
        Stop live display and finalize dry-run reporting/listeners.
        """
        self._stop_live_display()
        self._print_dry_run_summary_once()
        self._stop_dry_run_summary_listener()

    def _start_polling_progress_logger(self) -> None:
        """
        Start the INFO polling progress fallback listener.

        Notes
        -----
        Fallback listener errors are downgraded to warnings.
        """
        if self._self_polling_progress_logger is not None:
            return
        try:
            listener = _PollingProgressLogger()
            self._self_batcher._add_event_listener(listener=listener.on_event)
            self._self_polling_progress_logger = listener
            log_info(
                logger=log,
                event=(
                    "Live display disabled by terminal auto-detection; "
                    "using polling progress INFO logs"
                ),
            )
        except Exception as error:
            warnings.warn(
                message=f"Failed to start batchling polling progress logs: {error}",
                category=UserWarning,
                stacklevel=2,
            )

    def _start_live_display(self) -> None:
        """
        Start the Rich live display when enabled.

        Notes
        -----
        Display errors are downgraded to warnings to avoid breaking batching.
        """
        if self._self_live_display is not None or self._self_polling_progress_logger is not None:
            return
        if self._self_batcher._dry_run:
            return
        if not self._self_live_display_enabled:
            return
        if not should_enable_live_display(enabled=self._self_live_display_enabled):
            self._start_polling_progress_logger()
            return
        try:
            display = BatcherRichDisplay()
            self._self_batcher._add_event_listener(listener=display.on_event)
            display.start()
            self._self_live_display = display
            self._start_live_display_heartbeat()
        except Exception as error:
            warnings.warn(
                message=f"Failed to start batchling live display: {error}",
                category=UserWarning,
                stacklevel=2,
            )

    async def _run_live_display_heartbeat(self) -> None:
        """
        Periodically refresh the live display while the context is active.
        """
        try:
            while self._self_live_display is not None:
                self._self_live_display.refresh()
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            raise

    def _start_live_display_heartbeat(self) -> None:
        """
        Start the 1-second live display heartbeat when an event loop exists.
        """
        if self._self_live_display is None:
            return
        if self._self_live_display_heartbeat_task is not None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._self_live_display_heartbeat_task = loop.create_task(
            coro=self._run_live_display_heartbeat()
        )

    def _stop_live_display(self) -> None:
        """
        Stop and unregister the Rich live display.

        Notes
        -----
        Display shutdown errors are downgraded to warnings.
        """
        display = self._self_live_display
        fallback_listener = self._self_polling_progress_logger
        if display is None and fallback_listener is None:
            return
        self._self_live_display = None
        self._self_polling_progress_logger = None
        heartbeat_task = self._self_live_display_heartbeat_task
        self._self_live_display_heartbeat_task = None
        if heartbeat_task is not None and not heartbeat_task.done():
            heartbeat_task.cancel()
        try:
            if display is not None:
                self._self_batcher._remove_event_listener(listener=display.on_event)
                display.stop()
            if fallback_listener is not None:
                self._self_batcher._remove_event_listener(listener=fallback_listener.on_event)
        except Exception as error:
            warnings.warn(
                message=f"Failed to stop batchling live display: {error}",
                category=UserWarning,
                stacklevel=2,
            )

    def __enter__(self) -> None:
        """
        Enter the synchronous context manager and activate the batcher.

        Returns
        -------
        None
            ``None`` for scoped activation.
        """
        self._self_context_token = active_batcher.set(self._self_batcher)
        self._start_dry_run_summary_listener()
        self._start_live_display()
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> bool:
        """
        Exit the synchronous context manager and reset the batcher.

        Parameters
        ----------
        exc_type : type[BaseException] | None
            Exception type, if any.
        exc_val : BaseException | None
            Exception value, if any.
        exc_tb : typing.Any
            Exception traceback, if any.

        Returns
        -------
        bool
            ``True`` to suppress ``DryRunEarlyExit``, otherwise ``False``.
        """
        should_suppress = isinstance(exc_val, DryRunEarlyExit)
        if self._self_context_token is not None:
            active_batcher.reset(self._self_context_token)
            self._self_context_token = None
        try:
            loop = asyncio.get_running_loop()
            close_task = loop.create_task(coro=self._self_batcher.close())
            close_task.add_done_callback(self._on_sync_close_done)
        except RuntimeError:
            warnings.warn(
                message=(
                    "BatchingContext used with sync context manager. "
                    "Use 'async with' for proper cleanup, or manually call await "
                    "batcher.close()"
                ),
                category=UserWarning,
                stacklevel=2,
            )
            self._finalize_context_displays()
        return should_suppress

    def _on_sync_close_done(self, close_task: asyncio.Task[None]) -> None:
        """
        Callback run when sync-context close task completes.

        Parameters
        ----------
        close_task : asyncio.Task[None]
            Completed close task.
        """
        try:
            _ = close_task.result()
        except asyncio.CancelledError:
            pass
        except Exception as error:
            warnings.warn(
                message=f"Failed to close batcher in sync context: {error}",
                category=UserWarning,
                stacklevel=2,
            )
        self._finalize_context_displays()

    async def __aenter__(self) -> None:
        """
        Enter the async context manager and activate the batcher.

        Returns
        -------
        None
            ``None`` for scoped activation.
        """
        self._self_context_token = active_batcher.set(self._self_batcher)
        self._start_dry_run_summary_listener()
        self._start_live_display()
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> bool:
        """
        Exit the async context manager, reset the batcher, and flush pending work.

        Parameters
        ----------
        exc_type : type[BaseException] | None
            Exception type, if any.
        exc_val : BaseException | None
            Exception value, if any.
        exc_tb : typing.Any
            Exception traceback, if any.

        Returns
        -------
        bool
            ``True`` to suppress ``DryRunEarlyExit``, otherwise ``False``.
        """
        should_suppress = isinstance(exc_val, DryRunEarlyExit)
        if self._self_context_token is not None:
            active_batcher.reset(self._self_context_token)
            self._self_context_token = None
        try:
            await self._self_batcher.close()
        finally:
            self._finalize_context_displays()
        return should_suppress
