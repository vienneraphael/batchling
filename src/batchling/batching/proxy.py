"""
Actual function/instance wrapper that is returned by the `batchify` function.
We use wrapt to support isinstance checks and other magic methods that standard
__getattr__ wrapping does not support.
We also use __getattr__ overriding to recurse into the wrapped object when necessary
because wrapt.ObjectProxy does not support recursive attribute access.
"""

import asyncio
import functools
import inspect
import warnings
from typing import TYPE_CHECKING, Any, Generic, TypeVar

# Type variable for the wrapped object type
T = TypeVar("T")


if TYPE_CHECKING:
    from batchling.batching.core import Batcher

    class BatchingProxy(Generic[T]):
        """
        Proxy that wraps an object and sets batcher context on method calls.

        This proxy preserves the type of the wrapped object for IDE autocomplete
        and type checking. When you wrap a ``Client`` instance, the proxy will
        have all the same methods and attributes as ``Client``.

        During static analysis the constructor is typed as returning ``T`` so
        that IDEs provide full autocomplete and hover-signature information for
        the wrapped object's methods.

        Example::

            client = MockClient()
            proxy = BatchingProxy(client, batcher)
            proxy.sync_method(5)  # IDE shows MockClient.sync_method signature
        """

        _self_batcher: Batcher
        __wrapped__: T

        def __new__(cls, wrapped: T, batcher: Batcher) -> T: ...  # type: ignore[misc]
        def __init__(self, wrapped: T, batcher: Batcher) -> None: ...
        def __class_getitem__(cls, item: type) -> type: ...
        def __enter__(self) -> T: ...  # type: ignore[misc]
        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: Any,
        ) -> None: ...
        async def __aenter__(self) -> T: ...  # type: ignore[misc]
        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: Any,
        ) -> None: ...

else:
    import wrapt

    from batchling.batching.hooks import active_batcher

    class BatchingProxy(wrapt.ObjectProxy):
        """
        Proxy that wraps an object and sets batcher context on method calls.

        This proxy preserves the type of the wrapped object for IDE autocomplete
        and type checking. When you wrap a ``Client`` instance, the proxy will
        have all the same methods and attributes as ``Client``.

        Type parameter:
            T: The type of the wrapped object

        Example:
            >>> client = MockClient()
            >>> proxy: BatchingProxy[MockClient] = batchify(client)
            >>> proxy.sync_method(5)  # IDE will know this method exists
        """

        def __init__(self, wrapped, batcher):
            super().__init__(wrapped)
            # We store batcher on self, but be careful not to conflict with wrapped attrs
            self._self_batcher = batcher

        def __class_getitem__(cls, item):
            """Make BatchingProxy subscriptable for type hints: BatchingProxy[Client]"""
            return cls

        def __getattr__(self, name):
            # 1. Get the attribute from the wrapped object
            # (super().__getattr__ doesn't exist in wrapt, we access the wrapped obj directly)
            original_attr = getattr(self.__wrapped__, name)

            # 2. Check if we should wrap it
            # We don't wrap dunder methods, basic types, etc.
            if name.startswith("__") or isinstance(
                original_attr, (int, str, float, bool, list, dict)
            ):
                return original_attr

            # 3. If it's a method/function, we wrap it to Activate Context
            if callable(original_attr):
                # Check if the method is async
                is_async = inspect.iscoroutinefunction(original_attr)

                if is_async:

                    @functools.wraps(original_attr)
                    async def wrapper(*args, **kwargs):
                        token = active_batcher.set(self._self_batcher)
                        try:
                            return await original_attr(*args, **kwargs)
                        finally:
                            active_batcher.reset(token)
                else:

                    @functools.wraps(original_attr)
                    def wrapper(*args, **kwargs):
                        token = active_batcher.set(self._self_batcher)
                        try:
                            return original_attr(*args, **kwargs)
                        finally:
                            active_batcher.reset(token)

                return wrapper

            # 4. If it's an object (like 'chat' or 'completions'), RECURSE!
            # This keeps the chain alive.
            return BatchingProxy(original_attr, self._self_batcher)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            # Note: close() is async, so we can't properly close in a sync context manager.
            # Try to schedule it if there's an event loop running, otherwise warn.
            try:
                loop = asyncio.get_running_loop()
                # Schedule the close for later execution
                loop.create_task(self._self_batcher.close())
            except RuntimeError:
                # No event loop running - warn the user
                warnings.warn(
                    "BatchingProxy used with sync context manager. "
                    "Use 'async with' for proper cleanup, or manually call await proxy._self_batcher.close()",
                    UserWarning,
                    stacklevel=2,
                )

        # Async context manager support
        async def __aenter__(self):
            # When entering 'async with', we don't necessarily set the context globally
            # because the Proxy ALREADY sets it on every method call.
            # However, we can use this to initialize the batcher if needed.
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            # Crucial: Ensure the batcher flushes any remaining items and closes
            await self._self_batcher.close()
