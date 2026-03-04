# Rich display: live panel and dry-run summary rendering

`src/batchling/rich_display.py` renders batching progress to `stderr` using
Rich components, backed by shared state from `progress_state.py`.

## Responsibilities

- Render a live context progress panel (`BatcherRichDisplay`).
- Render a static dry-run summary panel (`DryRunSummaryDisplay`).
- Decide whether live display should auto-enable in the current terminal.

## `BatcherRichDisplay`

`BatcherRichDisplay` owns a `Live` instance and a `BatchProgressState`.

Event flow:

1. `on_event(event)` updates progress state.
2. display refresh rebuilds panel content from computed aggregates.

Panel composition:

- aggregate progress bar (`completed/total`, percent, elapsed time)
- request metrics line (total, cached, completed, in-progress)
- queue summary table (`provider`, `endpoint`, `model`, queue progress)

Queue progress cells are formatted as `completed/total (percent)`.

## `DryRunSummaryDisplay`

`DryRunSummaryDisplay` owns a `DryRunSummaryState` and prints one static report
panel with:

- totals line: batchable requests and cache-hit requests
- queue summary table: expected requests and expected batches per queue

This display is used at dry-run teardown, not as a live-updating panel.

## Auto-enable logic

`should_enable_live_display(enabled=...)` returns `True` only when:

- caller enabled live display
- `stderr` is a TTY
- `TERM` is not empty/`dumb`
- `CI` is not set

When this returns `False`, `BatchingContext` switches to INFO poll-progress
logging fallback instead of Rich live rendering.

## Code reference

- `src/batchling/rich_display.py`
- `src/batchling/progress_state.py`
- `src/batchling/context.py`
