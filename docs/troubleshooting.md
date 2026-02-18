# Troubleshooting

## Requests are not being batched

Check:

- The request targets a supported provider hostname.
- The endpoint is batchable for that provider.
- The call runs inside `batchify()` scope (or via `batchling` CLI wrapper).

## Script fails in CLI mode

Check:

- Target format is `path/to/script.py:function_name`.
- The function exists in that script.
- The function is `async def`.

## Batch completion feels slow

- Increase `batch_size` only if you have enough traffic to fill queues quickly.
- Reduce `batch_window_seconds` for lower queue wait time.
- Reduce `batch_poll_interval_seconds` to check finished batches more frequently.

## Validate setup safely

Run with dry-run to verify interception and queueing before real provider submissions:

```bash
batchling script.py:main --dry-run
```
