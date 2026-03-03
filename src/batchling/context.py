"""
Context manager returned by ``batchify``.
"""

import asyncio
import typing as t
import warnings

from batchling.core import Batcher
from batchling.hooks import active_batcher
from batchling.rich_display import (
    BatcherRichDisplay,
    LiveDisplayMode,
    should_enable_live_display,
)


class BatchingContext:
    """
    Context manager that activates a batcher for a scoped block.

    Parameters
    ----------
    batcher : Batcher
        Batcher instance used for the scope of the context manager.
    live_display : LiveDisplayMode, optional
        Live display mode used when entering the context.
    """

    def __init__(
        self,
        *,
        batcher: "Batcher",
        live_display: LiveDisplayMode = "auto",
    ) -> None:
        """
        Initialize the context manager.

        Parameters
        ----------
        batcher : Batcher
            Batcher instance used for the scope of the context manager.
        live_display : LiveDisplayMode, optional
            Live display mode used when entering the context.
        """
        self._self_batcher = batcher
        self._self_live_display_mode = live_display
        self._self_live_display: BatcherRichDisplay | None = None
        self._self_live_display_heartbeat_task: asyncio.Task[None] | None = None
        self._self_context_token: t.Any | None = None

    def _start_live_display(self) -> None:
        """
        Start the Rich live display when enabled.

        Notes
        -----
        Display errors are downgraded to warnings to avoid breaking batching.
        """
        if self._self_live_display is not None:
            return
        if not should_enable_live_display(mode=self._self_live_display_mode):
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
        if self._self_live_display is None:
            return
        display = self._self_live_display
        self._self_live_display = None
        heartbeat_task = self._self_live_display_heartbeat_task
        self._self_live_display_heartbeat_task = None
        if heartbeat_task is not None and not heartbeat_task.done():
            heartbeat_task.cancel()
        try:
            self._self_batcher._remove_event_listener(listener=display.on_event)
            display.stop()
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
        self._start_live_display()
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
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
        """
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
            self._stop_live_display()

    def _on_sync_close_done(self, _: asyncio.Task[None]) -> None:
        """
        Callback run when sync-context close task completes.

        Parameters
        ----------
        _ : asyncio.Task[None]
            Completed close task.
        """
        self._stop_live_display()

    async def __aenter__(self) -> None:
        """
        Enter the async context manager and activate the batcher.

        Returns
        -------
        None
            ``None`` for scoped activation.
        """
        self._self_context_token = active_batcher.set(self._self_batcher)
        self._start_live_display()
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
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
        """
        if self._self_context_token is not None:
            active_batcher.reset(self._self_context_token)
            self._self_context_token = None
        try:
            await self._self_batcher.close()
        finally:
            self._stop_live_display()
