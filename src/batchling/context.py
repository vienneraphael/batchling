"""
Context manager returned by ``batchify``.
"""

import asyncio
import typing as t
import warnings

from batchling.context_display import _DisplayReportLifecycleController
from batchling.core import Batcher
from batchling.exceptions import DryRunEarlyExit
from batchling.hooks import active_batcher


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
        self._self_display_report_controller = _DisplayReportLifecycleController(
            batcher=batcher,
            live_display_enabled=live_display,
        )
        self._self_context_token: t.Any | None = None

    def __enter__(self) -> None:
        """
        Enter the synchronous context manager and activate the batcher.

        Returns
        -------
        None
            ``None`` for scoped activation.
        """
        self._self_context_token = active_batcher.set(self._self_batcher)
        self._self_display_report_controller.start()
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
            self._self_display_report_controller.finalize()
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
        self._self_display_report_controller.finalize()

    async def __aenter__(self) -> None:
        """
        Enter the async context manager and activate the batcher.

        Returns
        -------
        None
            ``None`` for scoped activation.
        """
        self._self_context_token = active_batcher.set(self._self_batcher)
        self._self_display_report_controller.start()
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
            self._self_display_report_controller.finalize()
        return should_suppress
