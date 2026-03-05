# Display/report lifecycle: `context_display.py`

`src/batchling/context_display.py` contains internal lifecycle orchestration used by
`BatchingContext` to keep context activation and close semantics separate from
display/report behavior.

## Responsibilities

- Start display/report listeners when a context becomes active.
- Finalize display/report lifecycle on teardown through one public `finalize()` call.
- Run Rich live panel lifecycle (`BatcherRichDisplay`) when enabled and auto-detection passes.
- Register INFO polling fallback logs when Rich live display is auto-disabled.
- Register dry-run summary aggregation and print one static summary at teardown.
- Manage the optional async heartbeat task that refreshes live output.
- Downgrade display/report failures to warnings to avoid breaking batching.

## Lifecycle contract

`_DisplayReportLifecycleController` exposes:

- `start()`: initialize dry-run listener and live/fallback listeners.
- `finalize()`: stop live/fallback listeners, print dry-run summary once, and remove dry-run listener.

Both methods are idempotent at the behavior level and safe to call during cleanup paths.

## Boundaries

- `BatchingContext` owns contextvar activation/reset and `batcher.close()` choreography.
- `_DisplayReportLifecycleController` owns only display/report setup and teardown.
- `rich_display.py` owns rendering components and terminal auto-enable policy.

## Code reference

- `src/batchling/context_display.py`
- `src/batchling/context.py`
- `src/batchling/rich_display.py`
