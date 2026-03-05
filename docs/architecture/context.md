# Context manager: `BatchingContext`

`BatchingContext` is a lightweight context manager that activates an active `Batcher`
for a scoped block. It yields `None`, while all HTTP hooks read the active batcher from
a context variable.

## Responsibilities

- Activate the `active_batcher` context for the duration of a context block.
- Yield `None` for scope-only lifecycle control.
- Support sync and async context manager patterns for cleanup and context scoping.
- Delegate display/report lifecycle setup and teardown to `context_display.py`.

## Flow summary

1. `BatchingContext` stores the `Batcher` on initialization.
2. `__enter__`/`__aenter__` set the active batcher for the entire context block.
3. `__enter__`/`__aenter__` also call display/report lifecycle `start()` on the
   dedicated controller.
4. `__exit__` resets the context and schedules `batcher.close()` if an event loop is
   running (otherwise it warns).
5. `__aexit__` resets the context and awaits `batcher.close()` to flush pending work.
6. On teardown, context cleanup calls display/report lifecycle `finalize()` after close.

## Code reference

- `src/batchling/context.py`
- `src/batchling/context_display.py`
