# Progress state: shared lifecycle aggregation

`src/batchling/progress_state.py` tracks lifecycle-event state used by Rich
rendering and fallback progress logging.

## Responsibilities

- Maintain in-memory batch tracking keyed by `batch_id`.
- Compute aggregate progress/request metrics for one batching context.
- Aggregate queue-level running/completed batch counts.
- Aggregate dry-run totals and queue-level estimates.

## `BatchProgressState`

`BatchProgressState` consumes `BatcherEvent` payloads through `on_event(...)`
and updates tracked batches using parsed lifecycle enums:

- `parse_event_type(event=...)`
- `parse_event_source(event=...)`

Handled lifecycle behaviors include:

- mark/resize batches on `BATCH_PROCESSING`
- mark active polling on `BATCH_POLLED`
- mark terminal success/failure on `BATCH_TERMINAL` and `BATCH_FAILED`
- count resumed cache-hit samples on `CACHE_HIT_ROUTED` with
  `RESUMED_POLL` source

Computed outputs:

- `compute_progress()` -> `(completed_samples, total_samples, percent)`
- `compute_request_metrics()` ->
  `(total_samples, cached_samples, completed_samples, in_progress_samples)`
- `compute_queue_batch_counts()` ->
  rows `(provider, endpoint, model, running, completed)`
- `compute_elapsed_seconds()`

Completion classification treats terminal statuses containing
`fail/error/cancel/expired/timeout` as non-completed.

## `DryRunSummaryState`

`DryRunSummaryState` tracks dry-run estimates only:

- total requests that would be batched
- total cache-hit dry-run requests
- per-queue expected requests and expected batches

It updates from:

- `REQUEST_QUEUED`
- `BATCH_PROCESSING` with `DRY_RUN` source
- `CACHE_HIT_ROUTED` with `CACHE_DRY_RUN` source

Queue keys are derived from `event["queue_key"]` when present, with fallback to
`provider`/`endpoint`/`model` fields.

## Why this module exists

This keeps lifecycle aggregation logic out of UI/rendering code. Display layers
(`rich_display.py` and context fallback logger) consume computed metrics instead
of reimplementing event parsing.

## Code reference

- `src/batchling/progress_state.py`
- `src/batchling/lifecycle_events.py`
- `src/batchling/context.py`
- `src/batchling/rich_display.py`
