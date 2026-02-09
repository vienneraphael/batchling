# API surface: `batchify`

`batchify` is the public entry point that activates batching for either a callable or an
object instance. It installs global hooks, creates a `Batcher`, and then returns either a
decorated function or a `BatchingProxy` for instances.

## Responsibilities

- Install HTTP hooks once (idempotent).
- Construct a `Batcher` with configuration such as `batch_size` and `batch_window_seconds`.
- Wrap callables with a decorator that sets the active batcher in a context variable.
- Wrap objects with `BatchingProxy` so all method calls inherit the batching context.

## Inputs and outputs

- **Inputs**: a callable or instance plus batcher configuration keyword arguments.
- **Outputs**: a decorated callable or `BatchingProxy[T]` instance that preserves the wrapped type.

## Extension notes

- Any new hook types should be installed by `install_hooks()` so the behavior stays centralized.
- Configuration changes to `Batcher` should be surfaced through keyword arguments on `batchify`.

## Code reference

- `src/batchling/batching/api.py`
