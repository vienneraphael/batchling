"""
Main endpoint for users.
Exposes a `batchify` function that maps a target object (function or instance)
to a BatchingProxy object that activates a specific Batcher context
whenever any method on the wrapped object is called.
"""

import functools
import inspect
import typing as t

from batchling.batching.core import Batcher
from batchling.batching.hooks import active_batcher, install_hooks
from batchling.batching.proxy import BatchingProxy

P = t.ParamSpec(name="P")
R = t.TypeVar(name="R")

# Type variable for the wrapped object type
T = t.TypeVar(name="T")


@t.overload
def batchify(target: t.Callable[P, R], **kwargs: t.Any) -> t.Callable[P, R]:
    """
    Wrap a callable target while preserving its signature.

    Parameters
    ----------
    target : typing.Callable[P, R]
        Callable to wrap.
    **kwargs : typing.Any
        Batcher configuration (``batch_size``, ``batch_window_seconds``, etc.).

    Returns
    -------
    typing.Callable[P, R]
        Wrapped callable.
    """
    ...


@t.overload
def batchify(target: T, **kwargs: t.Any) -> BatchingProxy[T]:
    """
    Wrap an object instance while preserving its type.

    Parameters
    ----------
    target : T
        Instance to wrap.
    **kwargs : typing.Any
        Batcher configuration (``batch_size``, ``batch_window_seconds``, etc.).

    Returns
    -------
    BatchingProxy[T]
        Proxy wrapper.
    """
    ...


def batchify(
    target: t.Callable[..., t.Any] | t.Any, **kwargs: t.Any
) -> BatchingProxy[t.Any] | t.Callable[..., t.Any]:
    """
    Universal adapter.

    Parameters
    ----------
    target : typing.Callable[..., typing.Any] | typing.Any
        Function or object instance (client, agent, etc.).
    **kwargs : typing.Any
        Batcher configuration (``batch_size``, ``batch_window_seconds``, etc.).

    Returns
    -------
    BatchingProxy[typing.Any] | typing.Callable[..., typing.Any]
        Wrapped target (proxy or decorated function).

    Notes
    -----
    For better IDE autocomplete and type checking, use type annotations:

    >>> from batchling.batching import batchify
    >>> client = MyClient()
    >>> wrapped: BatchingProxy[MyClient] = batchify(client)
    >>> wrapped.my_method()  # IDE will know this method exists
    """
    # 1. Install hooks globally (idempotent)
    install_hooks()

    # 2. Create Batcher instance with provided configuration
    batcher = Batcher(**kwargs)

    # 3. If target is callable (function), return decorated function
    if callable(target) and not isinstance(target, type):
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

    # 4. If target is an object (instance), return BatchingProxy
    # The overloads ensure the return type is T where T is the input type
    return t.cast(
        typ=BatchingProxy[T],
        val=BatchingProxy(
            wrapped=target,
            batcher=batcher,
        ),
    )
