# Usage Patterns

## Choose the right execution style

### Use `async with batchify(...)` when

- You control the application code.
- You want explicit batching scope around a block of async calls.
- You need local tuning per workflow.

### Use `batchling script.py:function` when

- You want to run an existing async script with minimal edits.
- You need to pass function args from CLI.
- You want to automate batched script runs from CI or schedulers.

## Forwarding function arguments in CLI mode

```bash
batchling jobs/run_eval.py:main dataset_a --limit 200 --dry-run
```

- Positional tokens are forwarded as positional args.
- `--name value` or `--name=value` are forwarded as keyword args.
- Standalone flags like `--dry-run` are forwarded as boolean `True` keyword args.

## Dry run pattern

Use dry-run before production launch:

```python
async with batchify(dry_run=True):
    ...
```

Dry-run still intercepts and queues supported requests, but it skips provider submission and polling.
