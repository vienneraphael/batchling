# API surface: `batchify`

`batchify` is the public entry point that activates batching for a scoped context.
It installs global hooks, creates a `Batcher`, and returns a `BatchingContext` that
yields `None`. Import it from `batchling` or `batchling.batching`.

## Responsibilities

- Install HTTP hooks once (idempotent).
- Construct a `Batcher` with configuration such as `batch_size`,
  `batch_window_seconds`, `batch_poll_interval_seconds`, and `dry_run`.
- Return a `BatchingContext` to scope batching to a context manager.

## Inputs and outputs

- **Inputs**: batcher configuration arguments.
- **`dry_run` behavior**: when `dry_run=True`, requests are still intercepted, queued,
  and grouped using normal window/size triggers, but provider batch submission and polling
  are skipped. Requests resolve with synthetic `httpx.Response` objects marked with
  `x-batchling-dry-run: 1`.
- **Outputs**: `BatchingContext[None]` instance that yields `None`.

## Extension notes

- Any new hook types should be installed by `install_hooks()` so the behavior stays centralized.
- Configuration changes to `Batcher` should be surfaced through arguments on `batchify`.
- `batchify` only supports a pure context-manager lifecycle and does not accept a target.

## Code reference

- `src/batchling/batching/api.py`
