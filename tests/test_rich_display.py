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


def test_batcher_rich_display_consumes_events() -> None:
    """Test Rich display event handling and rendering lifecycle."""
    display = rich_display.BatcherRichDisplay(
        console=Console(file=io.StringIO(), force_terminal=False),
    )

    display.start()
    display.on_event(
        {
            "event_type": "request_queued",
            "timestamp": 1.0,
            "provider": "openai",
            "endpoint": "/v1/chat/completions",
            "model": "model-a",
            "queue_key": ("openai", "/v1/chat/completions", "model-a"),
            "pending_count": 1,
        }
    )
    display.on_event(
        {
            "event_type": "batch_submitting",
            "timestamp": 2.0,
            "provider": "openai",
            "endpoint": "/v1/chat/completions",
            "model": "model-a",
            "queue_key": ("openai", "/v1/chat/completions", "model-a"),
            "request_count": 1,
        }
    )
    display.on_event(
        {
            "event_type": "batch_processing",
            "timestamp": 3.0,
            "provider": "openai",
            "endpoint": "/v1/chat/completions",
            "model": "model-a",
            "queue_key": ("openai", "/v1/chat/completions", "model-a"),
            "batch_id": "batch-1",
            "source": "poll_start",
        }
    )
    display.on_event(
        {
            "event_type": "batch_terminal",
            "timestamp": 4.0,
            "provider": "openai",
            "endpoint": "/v1/chat/completions",
            "model": "model-a",
            "queue_key": ("openai", "/v1/chat/completions", "model-a"),
            "batch_id": "batch-1",
            "status": "completed",
        }
    )
    display.stop()

    queue_activity = display._queues[("openai", "/v1/chat/completions", "model-a")]
    assert queue_activity.pending_count == 0
    assert queue_activity.active_batches == 0
    assert queue_activity.submitted_batches == 1
    assert queue_activity.last_status == "completed"
    assert queue_activity.last_batch_id == "batch-1"
