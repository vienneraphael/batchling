"""
Main endpoint for users.
Exposes a `batchify` function that maps a target object to a BatchingContext
that activates a specific Batcher context for the duration of a context manager.
"""

import typing as t

from batchling.batching.context import BatchingContext
from batchling.batching.core import Batcher
from batchling.batching.hooks import install_hooks

# Type variable for the wrapped object type
T = t.TypeVar(name="T")


def batchify(
    target: T | None = None,
    batch_size: int = 50,
    batch_window_seconds: float = 2.0,
    batch_poll_interval_seconds: float = 10.0,
    dry_run: bool = False,
) -> BatchingContext[T | None]:
    """
    Context manager adapter.

    Parameters
    ----------
    target : typing.Any | None
        Object instance (client, agent, etc.), or ``None``.
    batch_size : int, optional
        Submit a batch when this many requests are queued for a provider.
    batch_window_seconds : float, optional
        Submit a provider batch after this many seconds, even if size not reached.
    batch_poll_interval_seconds : float, optional
        Poll active batches every this many seconds.
    dry_run : bool, optional
        If ``True``, intercept and batch requests without sending provider batches.
        Batched requests resolve to synthetic responses.

    Returns
    -------
    BatchingContext[typing.Any]
        Context manager that yields the provided target value.

    Notes
    -----
    For better IDE autocomplete and type checking, use type annotations:

    >>> from batchling.batching import batchify
    >>> client = MyClient()
    >>> with batchify(target=client) as active_client:
    ...     active_client.my_method()
    """
    # 1. Install hooks globally (idempotent)
    install_hooks()

    # 2. Create Batcher instance with provided configuration
    batcher = Batcher(
        batch_size=batch_size,
        batch_window_seconds=batch_window_seconds,
        batch_poll_interval_seconds=batch_poll_interval_seconds,
        dry_run=dry_run,
    )

    # 3. Reject callables to keep a single lifecycle model (context manager only).
    if target is not None and callable(target):
        raise TypeError(
            "batchify no longer supports callable targets. "
            "Pass an instance (or None) and use it as a context manager."
        )

    # 4. If target is an object (or None), return BatchingContext.
    return t.cast(
        typ=BatchingContext[T | None],
        val=BatchingContext(
            target=target,
            batcher=batcher,
        ),
    )
