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


def test_batcher_rich_display_shows_sent_batches() -> None:
    """Test sent-batch table tracks batch metadata and latest status."""
    display = rich_display.BatcherRichDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    display.start()
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
    polled_event: rich_display.BatcherEvent = {
        "event_type": "batch_polled",
        "timestamp": 2.0,
        "provider": "openai",
        "batch_id": "batch-1",
        "status": "running",
        "source": "active_poll",
    }
    terminal_event: rich_display.BatcherEvent = {
        "event_type": "batch_terminal",
        "timestamp": 3.0,
        "provider": "openai",
        "batch_id": "batch-1",
        "status": "completed",
        "source": "active_poll",
    }

    display.on_event(processing_event)
    display.on_event(polled_event)
    display.on_event(terminal_event)
    display.stop()

    batch = display._batches["batch-1"]
    assert batch.provider == "openai"
    assert batch.endpoint == "/v1/chat/completions"
    assert batch.model == "model-a"
    assert batch.size == 3
    assert batch.latest_status == "completed"


def test_batcher_rich_display_tracks_resumed_batch_size() -> None:
    """Test resumed cache-hit routing increments displayed batch size."""
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

    display.on_event(cache_event)
    display.on_event(cache_event)

    batch = display._batches["batch-cached-1"]
    assert batch.size == 2
    assert batch.latest_status == "resumed"
