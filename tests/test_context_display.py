"""Tests for display/report lifecycle control in batchling.context_display."""

import logging
import typing as t
import warnings

import pytest

from batchling.context_display import _DisplayReportLifecycleController
from batchling.core import Batcher
from batchling.lifecycle_events import BatcherEventSource, BatcherEventType


@pytest.fixture
def batcher() -> Batcher:
    """Create a Batcher instance for testing."""
    return Batcher(batch_size=10, batch_window_seconds=1.0)


@pytest.mark.asyncio
async def test_controller_starts_and_finalizes_live_display(
    batcher: Batcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Start and finalize should manage live display and heartbeat task."""

    class DummyDisplay:
        """Simple live-display stub."""

        def __init__(self) -> None:
            self.started = False
            self.stopped = False

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.stopped = True

        def refresh(self) -> None:
            return None

        def on_event(self, event: dict[str, t.Any]) -> None:
            del event

    dummy_display = DummyDisplay()
    monkeypatch.setattr("batchling.context_display.BatcherRichDisplay", lambda: dummy_display)
    monkeypatch.setattr(
        "batchling.context_display.should_enable_live_display", lambda **_kwargs: True
    )

    controller = _DisplayReportLifecycleController(
        batcher=batcher,
        live_display_enabled=True,
    )

    controller.start()

    assert dummy_display.started is True
    assert controller._self_live_display_heartbeat_task is not None
    assert not controller._self_live_display_heartbeat_task.done()

    controller.finalize()

    assert dummy_display.stopped is True
    assert controller._self_live_display_heartbeat_task is None


def test_controller_start_without_running_loop_skips_heartbeat(
    batcher: Batcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Controller should skip heartbeat when no event loop is running."""

    class DummyDisplay:
        """Simple live-display stub."""

        def __init__(self) -> None:
            self.started = False
            self.stopped = False

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.stopped = True

        def on_event(self, event: dict[str, t.Any]) -> None:
            del event

    dummy_display = DummyDisplay()
    monkeypatch.setattr("batchling.context_display.BatcherRichDisplay", lambda: dummy_display)
    monkeypatch.setattr(
        "batchling.context_display.should_enable_live_display", lambda **_kwargs: True
    )

    controller = _DisplayReportLifecycleController(
        batcher=batcher,
        live_display_enabled=True,
    )

    controller.start()
    assert dummy_display.started is True
    assert controller._self_live_display_heartbeat_task is None

    controller.finalize()
    assert dummy_display.stopped is True


def test_controller_uses_polling_progress_fallback_when_auto_disabled(
    batcher: Batcher,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Controller should register fallback polling logs when Rich is auto-disabled."""
    monkeypatch.setattr(
        "batchling.context_display.should_enable_live_display", lambda **_kwargs: False
    )
    controller = _DisplayReportLifecycleController(
        batcher=batcher,
        live_display_enabled=True,
    )

    caplog.set_level(level=logging.INFO, logger="batchling.context_display")

    controller.start()
    batcher._emit_event(
        event_type=BatcherEventType.BATCH_PROCESSING,
        batch_id="batch-1",
        request_count=4,
        source=BatcherEventSource.POLL_START,
    )
    batcher._emit_event(
        event_type=BatcherEventType.BATCH_POLLED,
        batch_id="batch-1",
        status="in_progress",
        source=BatcherEventSource.ACTIVE_POLL,
    )

    assert any("using polling progress INFO logs" in record.message for record in caplog.records)
    assert any("Live display fallback progress" in record.message for record in caplog.records)

    controller.finalize()
    controller.finalize()


def test_controller_skips_live_display_in_dry_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Controller should not start live display in dry-run mode."""

    class DummyDisplay:
        """Simple live-display stub."""

        def __init__(self) -> None:
            self.started = False

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            return None

        def on_event(self, event: dict[str, t.Any]) -> None:
            del event

    dummy_display = DummyDisplay()
    monkeypatch.setattr("batchling.context_display.BatcherRichDisplay", lambda: dummy_display)
    monkeypatch.setattr(
        "batchling.context_display.should_enable_live_display", lambda **_kwargs: True
    )

    dry_run_batcher = Batcher(
        batch_size=1,
        batch_window_seconds=1.0,
        dry_run=True,
        cache=False,
    )
    controller = _DisplayReportLifecycleController(
        batcher=dry_run_batcher,
        live_display_enabled=True,
    )

    controller.start()

    assert dummy_display.started is False

    controller.finalize()


def test_controller_prints_dry_run_summary_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Controller should print dry-run summary once even if finalized multiple times."""

    class DummyDryRunSummaryDisplay:
        """Minimal dry-run summary display stub."""

        def __init__(self) -> None:
            self.print_calls = 0

        def on_event(self, event: dict[str, t.Any]) -> None:
            del event

        def print_summary(self) -> None:
            self.print_calls += 1

    dry_run_display = DummyDryRunSummaryDisplay()
    monkeypatch.setattr("batchling.context_display.DryRunSummaryDisplay", lambda: dry_run_display)

    dry_run_batcher = Batcher(
        batch_size=1,
        batch_window_seconds=1.0,
        dry_run=True,
        cache=False,
    )
    controller = _DisplayReportLifecycleController(
        batcher=dry_run_batcher,
        live_display_enabled=False,
    )

    controller.start()
    controller.finalize()
    controller.finalize()

    assert dry_run_display.print_calls == 1


def test_controller_downgrades_display_errors_to_warnings(
    batcher: Batcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Controller should warn instead of raising on display start/stop failures."""

    class DummyDisplay:
        """Live display stub that fails on stop."""

        def start(self) -> None:
            return None

        def stop(self) -> None:
            raise RuntimeError("stop-failed")

        def on_event(self, event: dict[str, t.Any]) -> None:
            del event

    monkeypatch.setattr("batchling.context_display.BatcherRichDisplay", lambda: DummyDisplay())
    monkeypatch.setattr(
        "batchling.context_display.should_enable_live_display", lambda **_kwargs: True
    )

    controller = _DisplayReportLifecycleController(
        batcher=batcher,
        live_display_enabled=True,
    )

    with warnings.catch_warnings(record=True) as warnings_list:
        warnings.simplefilter(action="always")
        controller.start()
        controller.finalize()

    assert any(
        "Failed to stop batchling live display" in str(warning.message) for warning in warnings_list
    )


def test_controller_downgrades_live_display_start_error_to_warning(
    batcher: Batcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Controller should warn instead of raising when live display startup fails."""

    class FailingDisplay:
        """Display stub that fails during startup."""

        def start(self) -> None:
            raise RuntimeError("start-failed")

        def on_event(self, event: dict[str, t.Any]) -> None:
            del event

    monkeypatch.setattr("batchling.context_display.BatcherRichDisplay", lambda: FailingDisplay())
    monkeypatch.setattr(
        "batchling.context_display.should_enable_live_display", lambda **_kwargs: True
    )

    controller = _DisplayReportLifecycleController(
        batcher=batcher,
        live_display_enabled=True,
    )

    with warnings.catch_warnings(record=True) as warnings_list:
        warnings.simplefilter(action="always")
        controller.start()

    assert any(
        "Failed to start batchling live display" in str(warning.message)
        for warning in warnings_list
    )
