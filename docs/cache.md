# Cache

By default, batches requests are cached locally.

This is very useful for cases where the long-running process is interrupted:

- user locking computer if running locally
- network error on polling
- Server-side API error during polling

When you re-run a script using `batchling`, the batch requests belonging to batches that were already sent to remote servers are cached locally.

This ensures you are never invoiced twice or more for a given request.

Whenever a cache hit is made, the corresponding request skips the batch submission part and is directly sent to polling the batch it belonged to in the past, usually giving instant results too.

## Cache retention

Cache is kept locally and automatically cleaned up once it's 30 days old.

This duration aligns with what most Batch APIs share on the duration for which they keep exposing batch results.

## Cross-frameworks cache

The cache system is based on request hashing, which means that two requests that are strictly equal will create a cache hit.
While possible, it is not guaranteed that all frameworks build requests exactly the same way and thus we cannot guarantee cross-frameworks cache hits.

## Deactivating cache

If you ever need to deactivate cache, you can do this through the parameter:

- `cache=False` if you use the python SDK

- `--no-cache` if you use the CLI

## Next Steps

- See how [dry run](./dry-run.md) can help you plan that everything is ok before sending batches

- Check out [deferred execution](./deferred-mode.md) to run batches without long-running polling processes
