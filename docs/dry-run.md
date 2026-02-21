# Dry Run

`batchling` allow users to declare that they want to launch a dry run for their batching.

This feature exists for users to be able to debug and better understand what WILL happen when they ultimately disable the flag, giving them the transparency required to be confident in the library.

In practice, the dry run feature deactivates all batch submissions, but everything is done virtually, which means we can count incoming requests, number of batch we would have created, etc..

To put it simply, it provides users with an exact breakdown of what their batched inference run would have been for real.

## Activating dry run

Dry run is activated by setting up a flag in the CLI or SDK:

- `dry_run=True` if using the SDK

- `--dry-run` if using the CLI

## Next Steps

- Check out [deferred execution](./deferred-mode.md) to run batches without long-running polling processes

- See how [cache](./cache.md) is saved and for how long it is kept.
