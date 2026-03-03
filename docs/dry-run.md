# Dry Run

`batchling` allow users to declare that they want to launch a dry run for their batching.

This feature exists for users to be able to debug and better understand what WILL happen when they ultimately disable the flag, giving them the transparency required to be confident in the library.

In practice, dry-run deactivates all provider submissions while keeping the
internal batching path active (queueing, windowing, and per-queue grouping).

To put it simply, it provides users with an exact breakdown of what their
batched inference run would have been for real.

## Behavior details

- Requests are still intercepted and grouped by queue key
  `(provider, endpoint, model)`.
- Provider submission/polling is skipped.
- Intercepted requests raise `DryRunEarlyExit` instead of returning synthetic
  provider responses.
- The CLI catches `DryRunEarlyExit` and exits cleanly after printing the report.
- On context exit, batchling prints a static Rich summary with:
  - total requests that would have been batched
  - total requests that would have been cache hits
  - per-queue expected requests and expected batch counts

## SDK handling

When running the SDK directly, catch `DryRunEarlyExit` if you want to continue
control flow after the first intercepted request:

```python
from batchling import DryRunEarlyExit, batchify

try:
    async with batchify(dry_run=True):
        ...
except DryRunEarlyExit:
    pass
```

## Activating dry run

Dry run is activated by setting up a flag in the CLI or SDK:

- `dry_run=True` if using the SDK

- `--dry-run` if using the CLI

## Next Steps

- See how [cache](./cache.md) is saved and for how long it is kept.
