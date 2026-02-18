"""
Context manager returned by ``batchify``.
"""

import asyncio
import typing as t
import warnings

from batchling.core import Batcher
from batchling.hooks import active_batcher


class BatchingContext:
    """
    Context manager that activates a batcher for a scoped block.

    Parameters
    ----------
    batcher : Batcher
        Batcher instance used for the scope of the context manager.
    """

    def __init__(self, *, batcher: "Batcher") -> None:
        """
        Initialize the context manager.

        Parameters
        ----------
        batcher : Batcher
            Batcher instance used for the scope of the context manager.
        """
        self._self_batcher = batcher
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
            loop.create_task(coro=self._self_batcher.close())
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

    async def __aenter__(self) -> None:
        """
        Enter the async context manager and activate the batcher.

        Returns
        -------
        None
            ``None`` for scoped activation.
        """
        self._self_context_token = active_batcher.set(self._self_batcher)
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
        await self._self_batcher.close()
