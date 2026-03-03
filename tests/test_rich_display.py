"""Tests for Rich live display helpers."""

import io

from rich.console import Console

import batchling.rich_display as rich_display


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
        "event_type": "batch_processing",
        "timestamp": 1.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "queue_key": ("openai", "/v1/chat/completions", "model-a"),
        "batch_id": "batch-1",
        "request_count": 3,
        "source": "poll_start",
    }
    terminal_event: rich_display.BatcherEvent = {
        "event_type": "batch_terminal",
        "timestamp": 2.0,
        "provider": "openai",
        "batch_id": "batch-1",
        "status": "completed",
        "source": "active_poll",
    }
    failed_batch_event: rich_display.BatcherEvent = {
        "event_type": "batch_processing",
        "timestamp": 3.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "queue_key": ("openai", "/v1/chat/completions", "model-a"),
        "batch_id": "batch-2",
        "request_count": 2,
        "source": "poll_start",
    }
    failed_terminal_event: rich_display.BatcherEvent = {
        "event_type": "batch_terminal",
        "timestamp": 4.0,
        "provider": "openai",
        "batch_id": "batch-2",
        "status": "failed",
        "source": "active_poll",
    }

    display.on_event(processing_event)
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
        "event_type": "cache_hit_routed",
        "timestamp": 1.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "batch_id": "batch-cached-1",
        "source": "resumed_poll",
        "custom_id": "custom-1",
    }
    terminal_event: rich_display.BatcherEvent = {
        "event_type": "batch_terminal",
        "timestamp": 2.0,
        "provider": "openai",
        "batch_id": "batch-cached-1",
        "status": "completed",
        "source": "resumed_poll",
    }

    display.on_event(cache_event)
    display.on_event(cache_event)
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
        "event_type": "batch_processing",
        "timestamp": 100.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "queue_key": ("openai", "/v1/chat/completions", "model-a"),
        "batch_id": "batch-1",
        "request_count": 1,
        "source": "poll_start",
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
        "event_type": "cache_hit_routed",
        "timestamp": 200.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "batch_id": "batch-cached-1",
        "source": "resumed_poll",
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
        "event_type": "batch_processing",
        "timestamp": 1.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "queue_key": ("openai", "/v1/chat/completions", "model-a"),
        "batch_id": "batch-1",
        "request_count": 3,
        "source": "poll_start",
    }
    terminal_event_batch_1: rich_display.BatcherEvent = {
        "event_type": "batch_terminal",
        "timestamp": 2.0,
        "provider": "openai",
        "batch_id": "batch-1",
        "status": "completed",
        "source": "active_poll",
    }
    processing_event_batch_2: rich_display.BatcherEvent = {
        "event_type": "batch_processing",
        "timestamp": 3.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "queue_key": ("openai", "/v1/chat/completions", "model-a"),
        "batch_id": "batch-2",
        "request_count": 2,
        "source": "poll_start",
    }
    cache_event_batch_3: rich_display.BatcherEvent = {
        "event_type": "cache_hit_routed",
        "timestamp": 4.0,
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "model": "model-a",
        "batch_id": "batch-3",
        "source": "resumed_poll",
        "custom_id": "custom-1",
    }
    terminal_event_batch_3: rich_display.BatcherEvent = {
        "event_type": "batch_terminal",
        "timestamp": 5.0,
        "provider": "openai",
        "batch_id": "batch-3",
        "status": "completed",
        "source": "resumed_poll",
    }

    display.on_event(processing_event_batch_1)
    display.on_event(terminal_event_batch_1)
    display.on_event(processing_event_batch_2)
    display.on_event(cache_event_batch_3)
    display.on_event(cache_event_batch_3)
    display.on_event(terminal_event_batch_3)

    total_samples, cached_samples, completed_samples, in_progress_samples = (
        display._compute_request_metrics()
    )
    assert total_samples == 7
    assert cached_samples == 2
    assert completed_samples == 5
    assert in_progress_samples == 2


def test_batcher_rich_display_pending_batches_table_truncates_with_ellipsis() -> None:
    """Test pending table shows top2/ellipsis/last2 for more than five rows."""
    display = rich_display.BatcherRichDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    for batch_index in range(1, 7):
        processing_event: rich_display.BatcherEvent = {
            "event_type": "batch_processing",
            "timestamp": float(batch_index),
            "provider": "openai",
            "endpoint": f"/v1/endpoint/{batch_index}",
            "model": f"model-{batch_index}",
            "queue_key": ("openai", f"/v1/endpoint/{batch_index}", f"model-{batch_index}"),
            "batch_id": f"batch-{batch_index}",
            "request_count": batch_index,
            "source": "poll_start",
        }
        display.on_event(processing_event)

    table = display._build_pending_batches_table()
    batch_id_cells = table.columns[0]._cells

    assert len(batch_id_cells) == 5
    assert batch_id_cells[0] == "batch-1"
    assert batch_id_cells[1] == "batch-2"
    assert batch_id_cells[2] == "..."
    assert batch_id_cells[3] == "batch-5"
    assert batch_id_cells[4] == "batch-6"


def test_batcher_rich_display_pending_batches_excludes_terminal() -> None:
    """Test pending table includes only non-terminal batches."""
    display = rich_display.BatcherRichDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    pending_event: rich_display.BatcherEvent = {
        "event_type": "batch_processing",
        "timestamp": 1.0,
        "provider": "openai",
        "endpoint": "/v1/pending",
        "model": "model-pending",
        "queue_key": ("openai", "/v1/pending", "model-pending"),
        "batch_id": "batch-pending",
        "request_count": 1,
        "source": "poll_start",
    }
    completed_event: rich_display.BatcherEvent = {
        "event_type": "batch_processing",
        "timestamp": 2.0,
        "provider": "openai",
        "endpoint": "/v1/completed",
        "model": "model-completed",
        "queue_key": ("openai", "/v1/completed", "model-completed"),
        "batch_id": "batch-completed",
        "request_count": 1,
        "source": "poll_start",
    }
    terminal_event: rich_display.BatcherEvent = {
        "event_type": "batch_terminal",
        "timestamp": 3.0,
        "provider": "openai",
        "batch_id": "batch-completed",
        "status": "completed",
        "source": "active_poll",
    }

    display.on_event(pending_event)
    display.on_event(completed_event)
    display.on_event(terminal_event)

    pending_batches = display._get_pending_batches()
    assert len(pending_batches) == 1
    assert pending_batches[0].batch_id == "batch-pending"

    pending_line = display._build_pending_batches_line()
    assert "Pending batches: 1" in pending_line.plain
