# Context manager: `BatchingContext`

`BatchingContext` is a lightweight context manager that activates an active `Batcher`
for a scoped block. It yields `None`, while all HTTP hooks read the active batcher from
a context variable.

## Responsibilities

- Activate the `active_batcher` context for the duration of a context block.
- Yield `None` for scope-only lifecycle control.
- Support sync and async context manager patterns for cleanup and context scoping.
- Start and stop optional Rich live activity display while the context is active.
- In dry-run mode, aggregate and print a static Rich summary at teardown.

## Flow summary

1. `BatchingContext` stores the `Batcher` on initialization.
2. `__enter__`/`__aenter__` set the active batcher for the entire context block.
3. `__exit__` resets the context and schedules `batcher.close()` if an event loop is
   running (otherwise it warns).
4. If `live_display=True`, the context attempts to start Rich panel rendering at
   enter-time when terminal auto-detection passes (`TTY`, non-`dumb`, non-`CI`).
   Otherwise it registers an `INFO` logging fallback that emits progress at poll-time.
5. In dry-run mode, a dedicated summary listener is also registered at enter-time.
6. `__aexit__` resets the context and awaits `batcher.close()` to flush pending work.
7. On teardown, the context prints one static dry-run summary report when dry-run is enabled.
8. Display/listener cleanup runs after close completes.

## Code reference

- `src/batchling/context.py`
