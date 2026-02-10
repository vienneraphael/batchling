# Context manager: `BatchingContext`

`BatchingContext` is a lightweight context manager that activates an active `Batcher`
for a scoped block. It yields the original instance (if provided), while all HTTP hooks
read the active batcher from a context variable.

## Responsibilities

- Activate the `active_batcher` context for the duration of a context block.
- Yield the original target instance (if provided).
- Support sync and async context manager patterns for cleanup and context scoping.

## Flow summary

1. `BatchingContext` stores the `Batcher` on initialization.
2. `__enter__`/`__aenter__` set the active batcher for the entire context block.
3. `__exit__` resets the context and schedules `batcher.close()` if an event loop is
   running (otherwise it warns).
4. `__aexit__` resets the context and awaits `batcher.close()` to flush pending work.

## Code reference

- `src/batchling/batching/context.py`
