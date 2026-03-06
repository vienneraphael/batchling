"""Tests for Rich live display helpers."""

import io

from rich.console import Console
from rich.text import Text

import batchling.rich_display as rich_display
from batchling.lifecycle_events import BatcherEventSource, BatcherEventType


def test_should_enable_live_display_auto_in_interactive_terminal(
    monkeypatch,
) -> None:
    """Test auto mode enables display in interactive terminals."""

    class DummyStderr:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(rich_display.sys, "stderr", DummyStderr())
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("CI", raising=False)

    assert rich_display.should_enable_live_display(enabled=True) is True


def test_should_enable_live_display_auto_disabled_in_ci(monkeypatch) -> None:
    """Test auto mode disables display in CI environments."""

    class DummyStderr:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(rich_display.sys, "stderr", DummyStderr())
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("CI", "true")

    assert rich_display.should_enable_live_display(enabled=True) is False


def test_should_enable_live_display_disabled_by_flag(monkeypatch) -> None:
    """Test explicit disable always returns False."""

    class DummyStderr:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(rich_display.sys, "stderr", DummyStderr())
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("CI", raising=False)

    assert rich_display.should_enable_live_display(enabled=False) is False


def test_batcher_rich_display_computes_context_progress() -> None:
    """Test context progress is derived from completed batch sizes."""
    display = rich_display.BatcherRichDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    processing_event: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_PROCESSING,
        "timestamp": 1.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "queue_key": ("openai", "/v1/chat/completions", "model-a"),
        "batch_id": "batch-1",
        "request_count": 3,
        "source": BatcherEventSource.POLL_START,
    }
    polled_event: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_POLLED,
        "timestamp": 1.5,
        "provider": "openai",
        "batch_id": "batch-1",
        "status": "in_progress",
        "request_count": 3,
        "progress_completed": 3,
        "progress_percent": 100.0,
        "source": BatcherEventSource.ACTIVE_POLL,
    }
    terminal_event: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_TERMINAL,
        "timestamp": 2.0,
        "provider": "openai",
        "batch_id": "batch-1",
        "status": "completed",
        "source": BatcherEventSource.ACTIVE_POLL,
    }
    failed_batch_event: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_PROCESSING,
        "timestamp": 3.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "queue_key": ("openai", "/v1/chat/completions", "model-a"),
        "batch_id": "batch-2",
        "request_count": 2,
        "source": BatcherEventSource.POLL_START,
    }
    failed_terminal_event: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_TERMINAL,
        "timestamp": 4.0,
        "provider": "openai",
        "batch_id": "batch-2",
        "status": "failed",
        "source": BatcherEventSource.ACTIVE_POLL,
    }

    display.on_event(processing_event)
    display.on_event(polled_event)
    display.on_event(terminal_event)
    display.on_event(failed_batch_event)
    display.on_event(failed_terminal_event)

    completed_samples, total_samples, percent = display._compute_progress()
    assert completed_samples == 3
    assert total_samples == 5
    assert percent == 60.0


def test_batcher_rich_display_tracks_resumed_batch_progress() -> None:
    """Test resumed cache-hit routing contributes to total and completion."""
    display = rich_display.BatcherRichDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    cache_event: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.CACHE_HIT_ROUTED,
        "timestamp": 1.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "batch_id": "batch-cached-1",
        "source": BatcherEventSource.RESUMED_POLL,
        "custom_id": "custom-1",
    }
    terminal_event: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_TERMINAL,
        "timestamp": 2.0,
        "provider": "openai",
        "batch_id": "batch-cached-1",
        "status": "completed",
        "source": BatcherEventSource.RESUMED_POLL,
    }
    polled_event: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_POLLED,
        "timestamp": 1.5,
        "provider": "openai",
        "batch_id": "batch-cached-1",
        "status": "running",
        "request_count": 2,
        "progress_completed": 2,
        "progress_percent": 100.0,
        "source": BatcherEventSource.RESUMED_POLL,
    }

    display.on_event(cache_event)
    display.on_event(cache_event)
    display.on_event(polled_event)
    display.on_event(terminal_event)

    completed_samples, total_samples, percent = display._compute_progress()
    assert completed_samples == 2
    assert total_samples == 2
    assert percent == 100.0


def test_batcher_rich_display_elapsed_uses_first_batch_time(monkeypatch) -> None:
    """Test elapsed timer starts from first batch seen in the context."""
    current_time = {"value": 100.0}

    def fake_time() -> float:
        return current_time["value"]

    monkeypatch.setattr(rich_display.time, "time", fake_time)

    display = rich_display.BatcherRichDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    first_batch_event: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_PROCESSING,
        "timestamp": 100.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "queue_key": ("openai", "/v1/chat/completions", "model-a"),
        "batch_id": "batch-1",
        "request_count": 1,
        "source": BatcherEventSource.POLL_START,
    }
    display.on_event(first_batch_event)

    current_time["value"] = 127.0
    assert display._compute_elapsed_seconds() == 27
    assert display._format_elapsed(elapsed_seconds=27) == "00:00:27"


def test_batcher_rich_display_elapsed_starts_with_cache_batch(monkeypatch) -> None:
    """Test elapsed timer also starts when the first batch comes from cache routing."""
    current_time = {"value": 200.0}

    def fake_time() -> float:
        return current_time["value"]

    monkeypatch.setattr(rich_display.time, "time", fake_time)

    display = rich_display.BatcherRichDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    cache_event: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.CACHE_HIT_ROUTED,
        "timestamp": 200.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "batch_id": "batch-cached-1",
        "source": BatcherEventSource.RESUMED_POLL,
        "custom_id": "custom-1",
    }
    display.on_event(cache_event)

    current_time["value"] = 206.0
    assert display._compute_elapsed_seconds() == 6


def test_batcher_rich_display_request_metrics_line() -> None:
    """Test requests metrics aggregate total/cached/completed/in-progress samples."""
    display = rich_display.BatcherRichDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    processing_event_batch_1: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_PROCESSING,
        "timestamp": 1.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "queue_key": ("openai", "/v1/chat/completions", "model-a"),
        "batch_id": "batch-1",
        "request_count": 3,
        "source": BatcherEventSource.POLL_START,
    }
    terminal_event_batch_1: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_TERMINAL,
        "timestamp": 2.0,
        "provider": "openai",
        "batch_id": "batch-1",
        "status": "completed",
        "source": BatcherEventSource.ACTIVE_POLL,
    }
    polled_event_batch_1: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_POLLED,
        "timestamp": 1.5,
        "provider": "openai",
        "batch_id": "batch-1",
        "status": "running",
        "request_count": 3,
        "progress_completed": 3,
        "progress_percent": 100.0,
        "source": BatcherEventSource.ACTIVE_POLL,
    }
    processing_event_batch_2: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_PROCESSING,
        "timestamp": 3.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "queue_key": ("openai", "/v1/chat/completions", "model-a"),
        "batch_id": "batch-2",
        "request_count": 2,
        "source": BatcherEventSource.POLL_START,
    }
    cache_event_batch_3: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.CACHE_HIT_ROUTED,
        "timestamp": 4.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "batch_id": "batch-3",
        "source": BatcherEventSource.RESUMED_POLL,
        "custom_id": "custom-1",
    }
    terminal_event_batch_3: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_TERMINAL,
        "timestamp": 5.0,
        "provider": "openai",
        "batch_id": "batch-3",
        "status": "completed",
        "source": BatcherEventSource.RESUMED_POLL,
    }
    polled_event_batch_3: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_POLLED,
        "timestamp": 4.5,
        "provider": "openai",
        "batch_id": "batch-3",
        "status": "running",
        "request_count": 2,
        "progress_completed": 2,
        "progress_percent": 100.0,
        "source": BatcherEventSource.RESUMED_POLL,
    }

    display.on_event(processing_event_batch_1)
    display.on_event(polled_event_batch_1)
    display.on_event(terminal_event_batch_1)
    display.on_event(processing_event_batch_2)
    display.on_event(cache_event_batch_3)
    display.on_event(cache_event_batch_3)
    display.on_event(polled_event_batch_3)
    display.on_event(terminal_event_batch_3)

    total_samples, cached_samples, completed_samples, in_progress_samples = (
        display._compute_request_metrics()
    )
    assert total_samples == 7
    assert cached_samples == 2
    assert completed_samples == 5
    assert in_progress_samples == 2


def test_batcher_rich_display_queue_table_progress_column() -> None:
    """Test queue table progress column derives from completed/total counts."""
    display = rich_display.BatcherRichDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    queue_event_batch_1: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_PROCESSING,
        "timestamp": 1.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "queue_key": ("openai", "/v1/chat/completions", "model-a"),
        "batch_id": "batch-1",
        "request_count": 1,
        "source": BatcherEventSource.POLL_START,
    }
    queue_event_batch_2: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_PROCESSING,
        "timestamp": 2.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "queue_key": ("openai", "/v1/chat/completions", "model-a"),
        "batch_id": "batch-2",
        "request_count": 1,
        "source": BatcherEventSource.POLL_START,
    }
    terminal_event_batch_2: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_TERMINAL,
        "timestamp": 3.0,
        "provider": "openai",
        "batch_id": "batch-2",
        "status": "completed",
        "source": BatcherEventSource.ACTIVE_POLL,
    }
    polled_event_batch_2: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_POLLED,
        "timestamp": 2.5,
        "provider": "openai",
        "batch_id": "batch-2",
        "status": "running",
        "request_count": 1,
        "progress_completed": 1,
        "progress_percent": 100.0,
        "source": BatcherEventSource.ACTIVE_POLL,
    }
    other_queue_event: rich_display.BatcherEvent = {
        "event_type": BatcherEventType.BATCH_PROCESSING,
        "timestamp": 4.0,
        "provider": "groq",
        "endpoint": "/openai/v1/chat/completions",
        "model": "llama-3.1-8b-instant",
        "queue_key": ("groq", "/openai/v1/chat/completions", "llama-3.1-8b-instant"),
        "batch_id": "batch-3",
        "request_count": 1,
        "source": BatcherEventSource.POLL_START,
    }

    display.on_event(queue_event_batch_1)
    display.on_event(queue_event_batch_2)
    display.on_event(polled_event_batch_2)
    display.on_event(terminal_event_batch_2)
    display.on_event(other_queue_event)

    queue_rows = display._compute_queue_batch_counts()
    assert queue_rows == [
        ("groq", "/openai/v1/chat/completions", "llama-3.1-8b-instant", 1, 0),
        ("openai", "/v1/chat/completions", "model-a", 2, 1),
    ]

    table = display._build_queue_summary_table()
    assert table.columns[0].width == 12
    assert table.columns[1].width == 34
    assert table.columns[2].width == 28
    assert table.columns[3].width == 16
    assert table.columns[0]._cells == ["groq", "openai"]
    progress_cells = table.columns[3]._cells
    assert isinstance(progress_cells[0], Text)
    assert isinstance(progress_cells[1], Text)
    assert progress_cells[0].plain == "0/1 (0.0%)"
    assert progress_cells[1].plain == "1/2 (50.0%)"


def test_batcher_rich_display_terminal_status_does_not_imply_completion() -> None:
    """Test terminal events alone do not advance completed sample counts."""
    display = rich_display.BatcherRichDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    display.on_event(
        {
            "event_type": BatcherEventType.BATCH_PROCESSING,
            "timestamp": 1.0,
            "provider": "openai",
            "endpoint": "/v1/chat/completions",
            "model": "model-a",
            "queue_key": ("openai", "/v1/chat/completions", "model-a"),
            "batch_id": "batch-1",
            "request_count": 3,
            "source": BatcherEventSource.POLL_START,
        }
    )
    display.on_event(
        {
            "event_type": BatcherEventType.BATCH_TERMINAL,
            "timestamp": 2.0,
            "provider": "openai",
            "batch_id": "batch-1",
            "status": "completed",
            "source": BatcherEventSource.ACTIVE_POLL,
        }
    )

    completed_samples, total_samples, percent = display._compute_progress()
    assert completed_samples == 0
    assert total_samples == 3
    assert percent == 0.0


def test_batcher_rich_display_queue_table_empty_state() -> None:
    """Test queue table renders default row when no batches are tracked."""
    display = rich_display.BatcherRichDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    table = display._build_queue_summary_table()
    assert table.columns[0]._cells == ["-"]
    assert table.columns[1]._cells == ["-"]
    assert table.columns[2]._cells == ["-"]
    progress_cells = table.columns[3]._cells
    assert isinstance(progress_cells[0], Text)
    assert progress_cells[0].plain == "0/0 (0.0%)"


def test_batcher_rich_display_queue_progress_pads_to_total_width() -> None:
    """Test queue progress keeps parenthesis anchor stable for large totals."""
    progress_text = rich_display.BatcherRichDisplay._format_queue_progress(
        total=100,
        completed=1,
    )
    assert progress_text.plain == "  1/100 (1.0%)"


def test_dry_run_summary_display_aggregates_totals_and_queues() -> None:
    """Test dry-run static summary tracks expected totals and queue estimates."""
    display = rich_display.DryRunSummaryDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    display.on_event(
        {
            "event_type": BatcherEventType.REQUEST_QUEUED,
            "provider": "openai",
            "endpoint": "/v1/chat/completions",
            "model": "model-a",
            "queue_key": ("openai", "/v1/chat/completions", "model-a"),
            "custom_id": "1",
        }
    )
    display.on_event(
        {
            "event_type": BatcherEventType.REQUEST_QUEUED,
            "provider": "openai",
            "endpoint": "/v1/chat/completions",
            "model": "model-a",
            "queue_key": ("openai", "/v1/chat/completions", "model-a"),
            "custom_id": "2",
        }
    )
    display.on_event(
        {
            "event_type": BatcherEventType.REQUEST_QUEUED,
            "provider": "groq",
            "endpoint": "/openai/v1/chat/completions",
            "model": "llama-3.1-8b-instant",
            "queue_key": ("groq", "/openai/v1/chat/completions", "llama-3.1-8b-instant"),
            "custom_id": "3",
        }
    )
    display.on_event(
        {
            "event_type": BatcherEventType.BATCH_PROCESSING,
            "source": BatcherEventSource.DRY_RUN,
            "provider": "openai",
            "endpoint": "/v1/chat/completions",
            "model": "model-a",
            "queue_key": ("openai", "/v1/chat/completions", "model-a"),
            "request_count": 2,
        }
    )
    display.on_event(
        {
            "event_type": BatcherEventType.BATCH_PROCESSING,
            "source": BatcherEventSource.DRY_RUN,
            "provider": "groq",
            "endpoint": "/openai/v1/chat/completions",
            "model": "llama-3.1-8b-instant",
            "queue_key": ("groq", "/openai/v1/chat/completions", "llama-3.1-8b-instant"),
            "request_count": 1,
        }
    )
    display.on_event(
        {
            "event_type": BatcherEventType.CACHE_HIT_ROUTED,
            "source": BatcherEventSource.CACHE_DRY_RUN,
            "provider": "openai",
            "endpoint": "/v1/chat/completions",
            "model": "model-a",
            "batch_id": "batch-1",
            "custom_id": "4",
        }
    )

    totals_line = display._build_totals_line()
    assert totals_line.plain == "Batchable Requests: 3  -  Cache Hit Requests: 1"

    queue_table = display._build_queue_summary_table()
    assert queue_table.columns[0]._cells == ["groq", "openai"]
    assert queue_table.columns[3]._cells == ["1", "2"]
    assert queue_table.columns[4]._cells == ["1", "1"]


def test_dry_run_summary_display_queue_table_layout() -> None:
    """Test dry-run queue table keeps the shared queue column contract."""
    display = rich_display.DryRunSummaryDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    queue_table = display._build_queue_summary_table()
    assert [column.header for column in queue_table.columns] == [
        "provider",
        "endpoint",
        "model",
        "expected requests",
        "expected batches",
    ]
    assert queue_table.columns[0].width == 12
    assert queue_table.columns[1].width == 34
    assert queue_table.columns[2].width == 28
    assert queue_table.columns[3].width == 17
    assert queue_table.columns[4].width == 16


def test_dry_run_summary_display_renders_empty_state() -> None:
    """Test dry-run summary table defaults to zero row without events."""
    display = rich_display.DryRunSummaryDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )
    queue_table = display._build_queue_summary_table()
    assert queue_table.columns[0]._cells == ["-"]
    assert queue_table.columns[3]._cells == ["0"]
    assert queue_table.columns[4]._cells == ["0"]
