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

    assert rich_display.should_enable_live_display(mode="auto") is True


def test_should_enable_live_display_auto_disabled_in_ci(monkeypatch) -> None:
    """Test auto mode disables display in CI environments."""

    class DummyStderr:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(rich_display.sys, "stderr", DummyStderr())
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("CI", "true")

    assert rich_display.should_enable_live_display(mode="auto") is False


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
