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

P = t.ParamSpec("P")
R = t.TypeVar("R")

# Type variable for the wrapped object type
T = t.TypeVar("T")


@t.overload
def batchify(target: t.Callable[P, R], **kwargs: t.Any) -> t.Callable[P, R]:
    """Overload for callable targets (preserves the function signature for IDE autocomplete)."""
    ...


@t.overload
def batchify(target: T, **kwargs: t.Any) -> BatchingProxy[T]:
    """Overload for object instance targets (preserves the wrapped type for IDE autocomplete)."""
    ...


def batchify(
    target: t.Callable[..., t.Any] | t.Any, **kwargs: t.Any
) -> BatchingProxy[t.Any] | t.Callable[..., t.Any]:
    """
    Universal adapter.

    Args:
        target: Function or Object (Client, Agent, etc.)
        **kwargs: Batcher configuration (batch_size, batch_window_seconds, etc.)

    Returns:
        Wrapped target (Proxy or decorated function)

    Note:
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
        is_async = inspect.iscoroutinefunction(target)

        if is_async:

            @functools.wraps(target)
            async def decorated_function(*args: t.Any, **func_kwargs: t.Any) -> t.Any:
                token = active_batcher.set(batcher)
                try:
                    return await target(*args, **func_kwargs)
                finally:
                    active_batcher.reset(token)
        else:

            @functools.wraps(target)
            def decorated_function(*args: t.Any, **func_kwargs: t.Any) -> t.Any:
                token = active_batcher.set(batcher)
                try:
                    return target(*args, **func_kwargs)
                finally:
                    active_batcher.reset(token)

        return decorated_function

    # 4. If target is an object (instance), return BatchingProxy
    # The overloads ensure the return type is T where T is the input type
    return t.cast(BatchingProxy[T], BatchingProxy(target, batcher))
