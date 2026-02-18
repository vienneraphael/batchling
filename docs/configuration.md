# Configuration

batchling exposes four user-facing controls.

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
    dry_run=False,
):
    ...
```
