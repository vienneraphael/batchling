# Batching engine: `Batcher`

`Batcher` is the core queueing and lifecycle manager for batching requests. It collects
pending requests, triggers batch submission when size/time thresholds are reached, and
resolves futures back to callers.

## Responsibilities

- Maintain a pending queue protected by an async lock.
- Start a window timer when the first request arrives and submit when it elapses.
- Submit immediately when the pending queue reaches `batch_size`.
- Track active batches and resolve per-request futures with provider-parsed responses.
- Provide cleanup via `close()` to flush remaining work.

## Key data structures

- `_PendingRequest`: per-request data (custom ID, parameters, provider, and future).
- `_ActiveBatch`: a submitted batch with result tracking and request mapping.

## Lifecycle outline

1. `submit()` builds a `_PendingRequest` and queues it.
2. When thresholds are hit, `_submit_batch()` creates a new batch ID and attaches queued
   requests to an `_ActiveBatch` record.
3. Provider adapters convert batch results back into HTTP responses for each request.
4. `close()` flushes remaining requests and cancels timers.

## Extension notes

- Replace the placeholder submission behavior in `_submit_batch()` with actual provider
  batch API calls.
- Implement `_worker_loop()` to poll active batches and stream partial results.
