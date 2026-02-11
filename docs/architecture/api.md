# API surface: `batchify`

`batchify` is the public entry point that activates batching for an object instance (or
`None`). It installs global hooks, creates a `Batcher`, and returns a `BatchingContext`
for scoped activation. Import it from `batchling` or
`batchling.batching`.

## Responsibilities

- Install HTTP hooks once (idempotent).
- Construct a `Batcher` with configuration such as `batch_size`,
  `batch_window_seconds`, `batch_poll_interval_seconds`, and `dry_run`.
- Return a `BatchingContext` for instances to scope batching to a context manager.

## Inputs and outputs

- **Inputs**: an instance or `None` plus batcher configuration arguments.
- **`dry_run` behavior**: when `dry_run=True`, requests are still intercepted, queued,
  and grouped using normal window/size triggers, but provider batch submission and polling
  are skipped. Requests resolve with synthetic `httpx.Response` objects marked with
  `x-batchling-dry-run: 1`.
- **Outputs**: `BatchingContext[T]` instance that yields the target (or `None` when no
  target is supplied).

## Extension notes

- Any new hook types should be installed by `install_hooks()` so the behavior stays centralized.
- Configuration changes to `Batcher` should be surfaced through arguments on `batchify`.
- `batchify` raises a `TypeError` when passed any callable target. Use a context manager
  with an instance (or `None`) instead.

## Code reference

- `src/batchling/batching/api.py`
