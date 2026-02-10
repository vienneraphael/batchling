# API surface: `batchify`

`batchify` is the public entry point that activates batching for either a callable or an
object instance. It installs global hooks, creates a `Batcher`, and then returns either a
decorated function or a `BatchingContext` for instances. Import it from `batchling` or
`batchling.batching`.

## Responsibilities

- Install HTTP hooks once (idempotent).
- Construct a `Batcher` with configuration such as `batch_size`,
  `batch_window_seconds`, and `batch_poll_interval_seconds`.
- Wrap callables with a decorator that sets the active batcher in a context variable.
- Return a `BatchingContext` for instances to scope batching to a context manager.

## Inputs and outputs

- **Inputs**: a callable, instance, or `None` plus batcher configuration arguments.
- **Outputs**: a decorated callable or `BatchingContext[T]` instance that yields the target (or
  `None` when no target is supplied).

## Extension notes

- Any new hook types should be installed by `install_hooks()` so the behavior stays centralized.
- Configuration changes to `Batcher` should be surfaced through arguments on `batchify`.
- `batchify` raises a `TypeError` when passed a bound method. Use a context manager instead.

## Code reference

- `src/batchling/batching/api.py`
