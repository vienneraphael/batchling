# Proxy wrapper: `BatchingProxy`

`BatchingProxy` wraps an object instance and ensures every method call runs with the
active `Batcher` set in a context variable. It uses `wrapt.ObjectProxy` to preserve
introspection and `isinstance` behavior while supporting recursive attribute access.

## Responsibilities

- Preserve the wrapped object's type for IDE autocomplete and type checking.
- Set the `active_batcher` context around every method invocation (sync or async).
- Recurse into nested attributes (e.g., `client.chat.completions`) to keep batching
  active across namespaces.
- Support sync and async context manager patterns for cleanup and context scoping.

## Flow summary

1. `BatchingProxy` stores the `Batcher` on initialization.
2. `__getattr__` resolves the attribute on the wrapped object.
3. Callable attributes are wrapped with a context-setting wrapper.
4. Non-primitive attributes are wrapped recursively in another `BatchingProxy`.
5. `__enter__`/`__aenter__` set the active batcher for the entire context block.
6. `__exit__`/`__aexit__` reset the context and trigger `batcher.close()`.

## Code reference

- `src/batchling/batching/proxy.py`
