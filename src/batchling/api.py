"""
Main endpoint for users.
Exposes a `batchify` function that returns a BatchingContext that activates
the active Batcher for the duration of a context manager.
"""

from batchling.context import BatchingContext
from batchling.core import Batcher
from batchling.hooks import install_hooks


def batchify(
    batch_size: int = 50,
    batch_window_seconds: float = 2.0,
    batch_poll_interval_seconds: float = 10.0,
    dry_run: bool = False,
    cache: bool = True,
    deferred: bool = False,
    deferred_idle_seconds: float = 60.0,
) -> BatchingContext:
    """
    Context manager adapter.

    Parameters
    ----------
    batch_size : int, optional
        Submit a batch when this many requests are queued for a provider.
    batch_window_seconds : float, optional
        Submit a provider batch after this many seconds, even if size not reached.
    batch_poll_interval_seconds : float, optional
        Poll active batches every this many seconds.
    dry_run : bool, optional
        If ``True``, intercept and batch requests without sending provider batches.
        Batched requests resolve to synthetic responses.
    cache : bool, optional
        If ``True``, enable persistent request cache lookups.
    deferred : bool, optional
        If ``True``, allow deferred-mode idle termination while polling.
    deferred_idle_seconds : float, optional
        Idle threshold before deferred mode triggers a controlled early exit.

    Returns
    -------
    BatchingContext
        Context manager that yields ``None``.
    """
    # 1. Install hooks globally (idempotent)
    install_hooks()

    # 2. Create Batcher instance with provided configuration
    batcher = Batcher(
        batch_size=batch_size,
        batch_window_seconds=batch_window_seconds,
        batch_poll_interval_seconds=batch_poll_interval_seconds,
        dry_run=dry_run,
        cache=cache,
        deferred=deferred,
        deferred_idle_seconds=deferred_idle_seconds,
    )

    # 3. Return BatchingContext with no yielded target.
    return BatchingContext(
        batcher=batcher,
    )
