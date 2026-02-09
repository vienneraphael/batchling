# Batching engine: `Batcher`

`Batcher` is the core queueing and lifecycle manager for batching requests. It collects
pending requests, triggers batch submission when size/time thresholds are reached, and
resolves futures back to callers.

## Responsibilities

- Maintain per-provider pending queues protected by an async lock.
- Start a per-provider window timer when the first request arrives and submit when it elapses.
- Submit immediately when a provider queue reaches `batch_size`.
- Track active batches and resolve per-request futures with provider-parsed responses.
- Provide cleanup via `close()` to flush remaining work.

## Key data structures

- `_PendingRequest`: per-request data (custom ID, parameters, provider, and future).
- `_ActiveBatch`: a submitted batch with result tracking and request mapping.

## Lifecycle outline

1. `submit()` builds a `_PendingRequest` and queues it in the provider’s pending list.
2. When thresholds are hit, `_submit_requests()` starts a provider-specific batch submission task.
3. For OpenAI, the batcher uploads JSONL input to `/v1/files`, creates a `/v1/batches`
   job, then polls until results are ready.
4. Provider adapters convert batch results back into HTTP responses for each request.
5. `close()` flushes remaining requests and cancels timers.

## Extension notes

- Add new provider adapters by implementing batch submission + polling in `Batcher`.
- Implement `_worker_loop()` to stream partial results when providers support it.

## Code reference

- `src/batchling/batching/core.py`
