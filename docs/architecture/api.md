# API surface: `batchify`

`batchify` is the public entry point that activates batching for a scoped context.
It installs global hooks, creates a `Batcher`, and returns a `BatchingContext` that
yields `None`. Import it from `batchling`.

## Responsibilities

- Install HTTP hooks once (idempotent).
- Construct a `Batcher` with configuration such as `batch_size`,
  `batch_window_seconds`, `batch_poll_interval_seconds`, `dry_run`,
  `cache`, and `live_display`.
- Configure `batchling` logging defaults with Python's stdlib `logging`
  (`WARNING` by default).
- Return a `BatchingContext` to scope batching to a context manager.

## Inputs and outputs

- **Inputs**: batcher configuration arguments.
- **Queue semantics**: `batch_size` and `batch_window_seconds` are applied per
  strict queue key `(provider, endpoint, model)`.
- **`dry_run` behavior**: when `dry_run=True`, requests are still intercepted, queued,
  and grouped using normal window/size triggers, but provider batch submission and polling
  are skipped. Core resolves an internal dry-run abort signal, and hook boundaries
  convert that signal into `DryRunEarlyExit` when requests return through intercepted
  clients. Context teardown suppresses that dry-run exit for clean SDK output (no traceback)
  while still emitting the static dry-run summary report.
- **`cache` behavior**: when `cache=True` (default), intercepted requests are fingerprinted
  and looked up in a persistent request cache. Cache hits bypass queueing and resume polling
  from an existing provider batch when not in dry-run mode.
- **`live_display` behavior**: `live_display` is a boolean.
  When `True` (default), Rich panel rendering runs in auto mode and is enabled
  only when `stderr` is a TTY, terminal is not `dumb`, and `CI` is not set.
  If auto mode disables Rich, context-level progress is logged at `INFO` on
  polling events.
  When `False`, live display and fallback progress logs are both disabled.
- **Outputs**: `BatchingContext[None]` instance that yields `None`.
- **Logging**: lifecycle milestones are emitted at `INFO`, problems at
  `WARNING`/`ERROR`, and high-volume diagnostics at `DEBUG`. Request payloads
  and headers are never logged.

## CLI callable usage

The `batchling` CLI can execute an async callable from a script inside `batchify`:

```bash
batchling path/to/my_script.py:foo arg1 --name alice --count=3 --dry-run
```

Behavior:

- CLI options map directly to `batchify` arguments:
  `batch_size`, `batch_window_seconds`, `batch_poll_interval_seconds`, `dry_run`,
  `cache`, and `live_display`.
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
