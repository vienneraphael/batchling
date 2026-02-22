# Batching engine: `Batcher`

`Batcher` is the core queueing and lifecycle manager for batching requests. It collects
pending requests, triggers batch submission when size/time thresholds are reached, and
resolves futures back to callers.

## Responsibilities

- Maintain pending queues protected by an async lock, partitioned by
  `(provider, endpoint, model)`.
- Start a per-queue window timer when the first request arrives and submit when it elapses.
- Submit immediately when a queue reaches `batch_size`.
- Fingerprint intercepted requests and perform persistent cache lookups.
- Fast-track cache-hit requests to resumed polling instead of queueing/submitting.
- Delegate provider-specific batch submission to `provider.process_batch()`.
- Persist request-to-batch mappings on successful submission and clean old cache rows.
- Track active batches and resolve per-request futures with provider-parsed responses.
- Provide cleanup via `close()` to flush remaining work.

## Key data structures

- `_PendingRequest`: per-request data (custom ID, parameters, provider, and future).
- `_ActiveBatch`: a submitted batch with result tracking and request mapping.
- `_ResumedBatch`: cache-hit polling state keyed by `(provider, host, batch_id)`.

## Lifecycle outline

1. `submit()` computes queue key `(provider, endpoint, model)` and request fingerprint.
2. If cache hit: request is attached to `_ResumedBatch` and one resumed poller is reused.
3. If cache miss: request is enqueued under its queue key.
4. Threshold/window trigger calls `_submit_requests()` and starts provider batch submission.
5. On successful submission, request cache rows are upserted and stale rows are cleaned.
6. Batcher polls active batches and maps provider results back to request futures.
7. `close()` flushes remaining requests and cancels timers.

In `dry_run` mode, step 3 and provider polling are bypassed: `_process_batch()` still
creates `_ActiveBatch` for tracking, then resolves each request immediately with a
synthetic `httpx.Response` (`200`) marked with `x-batchling-dry-run: 1`.
Cache lookups remain enabled in dry-run mode for hit accounting, but cache writes are disabled.

## Extension notes

- Add new provider adapters by implementing `process_batch()` in the provider class.
- Ensure each provider declares `terminal_states` so polling termination is
  provider-specific.
- Keep polling/result resolution behavior in `Batcher` unless provider APIs diverge.

## Code reference

- `src/batchling/core.py`
