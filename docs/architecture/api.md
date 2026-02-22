# API surface: `batchify`

`batchify` is the public entry point that activates batching for a scoped context.
It installs global hooks, creates a `Batcher`, and returns a `BatchingContext` that
yields `None`. Import it from `batchling`.

## Responsibilities

- Install HTTP hooks once (idempotent).
- Construct a `Batcher` with configuration such as `batch_size`,
  `batch_window_seconds`, `batch_poll_interval_seconds`, `dry_run`,
  and `cache`.
- Return a `BatchingContext` to scope batching to a context manager.

## Inputs and outputs

- **Inputs**: batcher configuration arguments.
- **Queue semantics**: `batch_size` and `batch_window_seconds` are applied per
  strict queue key `(provider, endpoint, model)`.
- **`dry_run` behavior**: when `dry_run=True`, requests are still intercepted, queued,
  and grouped using normal window/size triggers, but provider batch submission and polling
  are skipped. Requests resolve with synthetic `httpx.Response` objects marked with
  `x-batchling-dry-run: 1`.
- **`cache` behavior**: when `cache=True` (default), intercepted requests are fingerprinted
  and looked up in a persistent request cache. Cache hits bypass queueing and resume polling
  from an existing provider batch when not in dry-run mode.
- **Outputs**: `BatchingContext[None]` instance that yields `None`.

## CLI callable usage

The `batchling` CLI can execute an async callable from a script inside `batchify`:

```bash
batchling path/to/my_script.py:foo arg1 --name alice --count=3 --dry-run
```

Behavior:

- CLI options map directly to `batchify` arguments:
  `batch_size`, `batch_window_seconds`, `batch_poll_interval_seconds`, `dry_run`,
  and `cache`.
- Script target must use `module_path:function_name` syntax.
- Forwarded callable arguments are mapped as:
  positional tokens are passed as positional arguments;
  `--name value` and `--name=value` are passed as keyword arguments.
- Standalone `--flag` tokens are passed as boolean keyword arguments with `True`.
- The script file is loaded with `runpy.run_path(..., run_name="batchling.runtime")`
  and the target async callable is awaited.

## Extension notes

- Any new hook types should be installed by `install_hooks()` so the behavior stays centralized.
- Configuration changes to `Batcher` should be surfaced through arguments on `batchify`.
- `batchify` only supports a pure context-manager lifecycle and does not accept a target.

## Code reference

- `src/batchling/api.py`
