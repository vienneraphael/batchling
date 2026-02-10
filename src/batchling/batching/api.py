"""
Main endpoint for users.
Exposes a `batchify` function that maps a target object (function or instance)
to a BatchingContext object that activates a specific Batcher context
for the duration of a context manager.
"""

import functools
import inspect
import types
import typing as t

from batchling.batching.context import BatchingContext
from batchling.batching.core import Batcher
from batchling.batching.hooks import active_batcher, install_hooks

P = t.ParamSpec(name="P")
R = t.TypeVar(name="R")

# Type variable for the wrapped object type
T = t.TypeVar(name="T")


@t.overload
def batchify(
    target: t.Callable[P, R],
    batch_size: int = 50,
    batch_window_seconds: float = 2.0,
    batch_poll_interval_seconds: float = 10.0,
) -> t.Callable[P, R]:
    """
    Wrap a callable target while preserving its signature.

    Parameters
    ----------
    target : typing.Callable[P, R]
        Callable to wrap.
    batch_size : int, optional
        Submit a batch when this many requests are queued for a provider.
    batch_window_seconds : float, optional
        Submit a provider batch after this many seconds, even if size not reached.
    batch_poll_interval_seconds : float, optional
        Poll active batches every this many seconds.

    Returns
    -------
    typing.Callable[P, R]
        Wrapped callable.
    """
    ...


@t.overload
def batchify(
    target: T,
    batch_size: int = 50,
    batch_window_seconds: float = 2.0,
    batch_poll_interval_seconds: float = 10.0,
) -> BatchingContext[T]:
    """
    Wrap an object instance while preserving its type.

    Parameters
    ----------
    target : T
        Instance to wrap.
    batch_size : int, optional
        Submit a batch when this many requests are queued for a provider.
    batch_window_seconds : float, optional
        Submit a provider batch after this many seconds, even if size not reached.
    batch_poll_interval_seconds : float, optional
        Poll active batches every this many seconds.

    Returns
    -------
    BatchingContext[T]
        Context manager that yields the target.
    """
    ...


@t.overload
def batchify(
    target: type[T],
    batch_size: int = 50,
    batch_window_seconds: float = 2.0,
    batch_poll_interval_seconds: float = 10.0,
) -> BatchingContext[type[T]]:
    """
    Wrap a class object in a batching context manager.

    Parameters
    ----------
    target : type[T]
        Class object to yield from the context manager.
    batch_size : int, optional
        Submit a batch when this many requests are queued for a provider.
    batch_window_seconds : float, optional
        Submit a provider batch after this many seconds, even if size not reached.
    batch_poll_interval_seconds : float, optional
        Poll active batches every this many seconds.

    Returns
    -------
    BatchingContext[type[T]]
        Context manager that yields the class object.
    """
    ...


@t.overload
def batchify(
    target: None = None,
    batch_size: int = 50,
    batch_window_seconds: float = 2.0,
    batch_poll_interval_seconds: float = 10.0,
) -> BatchingContext[None]:
    """
    Create a batching context manager without binding to a specific instance.

    Parameters
    ----------
    target : None, optional
        When omitted, the context manager yields ``None``.
    batch_size : int, optional
        Submit a batch when this many requests are queued for a provider.
    batch_window_seconds : float, optional
        Submit a provider batch after this many seconds, even if size not reached.
    batch_poll_interval_seconds : float, optional
        Poll active batches every this many seconds.

    Returns
    -------
    BatchingContext[None]
        Context manager that yields ``None``.
    """
    ...


def batchify(
    target: t.Callable[..., t.Any] | t.Any | None = None,
    batch_size: int = 50,
    batch_window_seconds: float = 2.0,
    batch_poll_interval_seconds: float = 10.0,
) -> BatchingContext[t.Any] | t.Callable[..., t.Any]:
    """
    Universal adapter.

    Parameters
    ----------
    target : typing.Callable[..., typing.Any] | typing.Any | None
        Function, object instance (client, agent, etc.), or ``None``.
    batch_size : int, optional
        Submit a batch when this many requests are queued for a provider.
    batch_window_seconds : float, optional
        Submit a provider batch after this many seconds, even if size not reached.
    batch_poll_interval_seconds : float, optional
        Poll active batches every this many seconds.

    Returns
    -------
    BatchingContext[typing.Any] | typing.Callable[..., typing.Any]
        Context manager (if target is not callable) or decorated function.

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
    )

    # 3. If target is a bound method, reject it to prevent misuse.
    if target is not None and isinstance(target, types.MethodType) and target.__self__ is not None:
        raise TypeError(
            "batchify should only be called on functions. "
            "Use a context manager for client methods instead."
        )

    # 4. If target is callable (function), return decorated function
    if target is not None and callable(target) and not isinstance(target, type):
        # Check if it's a class (type) - we don't want to wrap classes, only instances
        # For functions, create a decorator that sets the batcher context

        # Check if the function is a coroutine function
        is_async = inspect.iscoroutinefunction(obj=target)

        if is_async:

            @functools.wraps(wrapped=target)
            async def decorated_function(*args: t.Any, **func_kwargs: t.Any) -> t.Any:
                """
                Execute the wrapped coroutine under the active batcher context.

                Parameters
                ----------
                *args : typing.Any
                    Positional arguments forwarded to the target.
                **func_kwargs : typing.Any
                    Keyword arguments forwarded to the target.

                Returns
                -------
                typing.Any
                    Target return value.
                """
                token = active_batcher.set(batcher)
                try:
                    return await target(*args, **func_kwargs)
                finally:
                    active_batcher.reset(token)
        else:

            @functools.wraps(wrapped=target)
            def decorated_function(*args: t.Any, **func_kwargs: t.Any) -> t.Any:
                """
                Execute the wrapped function under the active batcher context.

                Parameters
                ----------
                *args : typing.Any
                    Positional arguments forwarded to the target.
                **func_kwargs : typing.Any
                    Keyword arguments forwarded to the target.

                Returns
                -------
                typing.Any
                    Target return value.
                """
                token = active_batcher.set(batcher)
                try:
                    return target(*args, **func_kwargs)
                finally:
                    active_batcher.reset(token)

        return decorated_function

    # 5. If target is an object (or None), return BatchingContext
    return t.cast(
        typ=BatchingContext[T],
        val=BatchingContext(
            target=target,
            batcher=batcher,
        ),
    )
