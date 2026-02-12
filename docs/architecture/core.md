# Batching engine: `Batcher`

`Batcher` is the core queueing and lifecycle manager for batching requests. It collects
pending requests, triggers batch submission when size/time thresholds are reached, and
resolves futures back to callers.

## Responsibilities

- Maintain per-provider pending queues protected by an async lock.
- Start a per-provider window timer when the first request arrives and submit when it elapses.
- Submit immediately when a provider queue reaches `batch_size`.
- Delegate provider-specific batch submission to `provider.process_batch()`.
- Track active batches and resolve per-request futures with provider-parsed responses.
- Provide cleanup via `close()` to flush remaining work.

## Key data structures

- `_PendingRequest`: per-request data (custom ID, parameters, provider, and future).
- `_ActiveBatch`: a submitted batch with result tracking and request mapping.

## Lifecycle outline

1. `submit()` builds a `_PendingRequest` and queues it in the provider’s pending list.
2. When thresholds are hit, `_submit_requests()` starts a provider-specific batch submission task.
3. The provider submits the batch job and returns poll metadata (`base_url`, headers,
   batch ID).
4. The batcher creates `_ActiveBatch`, polls for completion using
   `provider.terminal_states`, and resolves futures.
5. Provider adapters convert batch results back into HTTP responses for each request.
6. `close()` flushes remaining requests and cancels timers.

In `dry_run` mode, step 3 and provider polling are bypassed: `_process_batch()` still
creates `_ActiveBatch` for tracking, then resolves each request immediately with a
synthetic `httpx.Response` (`200`) marked with `x-batchling-dry-run: 1`.

## Extension notes

- Add new provider adapters by implementing `process_batch()` in the provider class.
- Ensure each provider declares `terminal_states` so polling termination is
  provider-specific.
- Keep polling/result resolution behavior in `Batcher` unless provider APIs diverge.

## Code reference

- `src/batchling/batching/core.py`
