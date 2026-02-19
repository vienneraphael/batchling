# Configuration

batchling exposes user-facing controls for queueing, polling, caching, and deferred mode.

## `batch_size`

- Type: `int`
- Default: `50`
- Meaning: submit when this many queued requests exist for a queue key.

## `batch_window_seconds`

- Type: `float`
- Default: `2.0`
- Meaning: submit when this time elapses, even if `batch_size` is not reached.

## `batch_poll_interval_seconds`

- Type: `float`
- Default: `10.0`
- Meaning: polling interval for active provider batches.

## `dry_run`

- Type: `bool`
- Default: `False`
- Meaning: intercept and group requests without sending provider batches.

## `cache`

- Type: `bool`
- Default: `True`
- Meaning: enable persistent request cache lookup and writeback for batch submissions.
- CLI: disable with `--no-cache`.

## `deferred`

- Type: `bool`
- Default: `False`
- Meaning: allow early termination when runtime becomes polling-only and idle.
- Behavior: raises `DeferredExit` for library usage; CLI catches it and exits successfully.

## `deferred_idle_seconds`

- Type: `float`
- Default: `60.0`
- Meaning: idle duration threshold before deferred mode triggers early exit.

## Queue semantics

Batch queues are partitioned by strict key:

- `provider`
- `endpoint`
- `model`

This means thresholds apply per `(provider, endpoint, model)` group, not globally.

## Example tuning

```python
async with batchify(
    batch_size=200,
    batch_window_seconds=5.0,
    batch_poll_interval_seconds=15.0,
    cache=True,
    deferred=False,
    deferred_idle_seconds=60.0,
    dry_run=False,
):
    ...
```
