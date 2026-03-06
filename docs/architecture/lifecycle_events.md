# Lifecycle events: typed contract

`src/batchling/lifecycle_events.py` centralizes the lifecycle event contract used by
`Batcher` emitters, progress consumers, and tests.

## What this module brings

- A single source of truth for lifecycle event identifiers.
- A single source of truth for lifecycle event sources.
- A typed listener payload model that stays dict-shaped for compatibility.
- Parse helpers that normalize incoming event payloads safely.
- A shared listener callable alias to avoid per-module redefinition.

## Core building blocks

### `BatcherEventType` (`StrEnum`)

Typed lifecycle event identifiers:

- `cache_hit_routed`
- `request_queued`
- `window_timer_error`
- `batch_submitting`
- `batch_processing`
- `batch_terminal`
- `batch_failed`
- `batch_polled`
- `missing_results`
- `final_flush_submitting`

### `BatcherEventSource` (`StrEnum`)

Typed source identifiers for lifecycle emissions:

- `cache_dry_run`
- `resumed_poll`
- `window_timer`
- `dry_run`
- `submit`
- `poll_start`
- `active_poll`
- `resumed_results`
- `results`
- `close`

### `BatcherEvent` (`TypedDict`)

Dict-shaped lifecycle payload used by listeners. This preserves backward compatibility
for consumers using `event.get(...)` or `event["event_type"]`.

Poll events (`batch_polled`) may include sample-granular progress fields:

- `request_count`
- `progress_completed`
- `progress_percent`

### Parse helpers

- `parse_event_type(event=...) -> BatcherEventType | None`
- `parse_event_source(event=...) -> BatcherEventSource | None`

These helpers tolerate unknown/malformed payloads by returning `None` instead of
raising, which keeps listener pipelines resilient.

### `BatcherEventListener`

Shared callable alias:

- `t.Callable[[BatcherEvent], None]`

## Why this reduces coupling

- Emitters no longer depend on ad-hoc string literals spread across modules.
- Consumers branch on shared enums instead of duplicating raw string checks.
- Tests assert against shared constants, reducing drift between production code and test fixtures.
- Event additions/changes now have one explicit place to update first.

## Compatibility and behavior

- Listener-facing payloads remain dict-like and key-compatible.
- Existing keys/values are preserved; this is a typing and maintainability improvement,
  not a runtime behavior redesign.
- Unknown event types/sources are ignored safely by parser-driven consumers.

## Extension workflow

When introducing a new lifecycle event:

1. Add the new enum member(s) in `BatcherEventType` and, if needed, `BatcherEventSource`.
2. Add/update the corresponding `Batcher` emitter helper signature and payload.
3. Update consumers to use parsed enum branches where relevant.
4. Update tests to assert with shared constants.

## Code reference

- `src/batchling/lifecycle_events.py`
- `src/batchling/core.py`
- `src/batchling/progress_state.py`
- `src/batchling/context.py`
