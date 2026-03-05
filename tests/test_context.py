"""
Tests for the BatchingContext class in batchling.context.
"""

import asyncio
import logging
import typing as t
import warnings
from unittest.mock import AsyncMock, patch

import pytest

from batchling.context import BatchingContext
from batchling.core import Batcher, _DryRunAbortSignal
from batchling.exceptions import DryRunEarlyExit
from batchling.hooks import active_batcher
from batchling.lifecycle_events import BatcherEventSource, BatcherEventType
from batchling.providers.openai import OpenAIProvider


@pytest.fixture
def batcher() -> Batcher:
    """Create a Batcher instance for testing."""
    return Batcher(batch_size=10, batch_window_seconds=1.0)


def test_batching_context_initialization(batcher: Batcher) -> None:
    """Test that BatchingContext initializes correctly."""
    context = BatchingContext(batcher=batcher)

    assert context._self_batcher is batcher


def test_batching_context_enters_and_exits_sync(batcher: Batcher, reset_context: None) -> None:
    """Test that BatchingContext activates the batcher in a sync scope."""
    context = BatchingContext(batcher=batcher)

    assert active_batcher.get() is None

    with patch.object(target=batcher, attribute="close", new_callable=AsyncMock):
        with context as active_client:
            assert active_batcher.get() is batcher
            assert active_client is None
        assert active_batcher.get() is None


def test_batching_context_sync_warns_without_loop(
    batcher: Batcher,
    reset_context: None,
) -> None:
    """Test that sync context manager warns when no event loop is running."""
    context = BatchingContext(batcher=batcher)

    try:
        _ = asyncio.get_running_loop()
        skip = t.cast(typ=t.Callable[[str], t.NoReturn], val=pytest.skip)
        skip("Event loop is already running")
    except RuntimeError:
        pass

    with warnings.catch_warnings(record=True) as warnings_list:
        warnings.simplefilter(action="always")
        with context as active_client:
            assert active_batcher.get() is batcher
            assert active_client is None

        assert len(warnings_list) > 0
        assert any(
            "sync context manager" in str(warning.message).lower() for warning in warnings_list
        )
    assert active_batcher.get() is None


@pytest.mark.asyncio
async def test_batching_context_async_closes_batcher(
    batcher: Batcher,
    reset_context: None,
) -> None:
    """Test that async context manager closes the batcher."""
    context = BatchingContext(batcher=batcher)

    with patch.object(
        target=batcher,
        attribute="close",
        new_callable=AsyncMock,
    ) as mock_close:
        async with context as active_client:
            assert active_batcher.get() is batcher
            assert active_client is None
        assert active_batcher.get() is None

        mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_batching_context_without_target(batcher: Batcher, reset_context: None) -> None:
    """Test that BatchingContext yields None."""
    context = BatchingContext(batcher=batcher)

    async with context as active_target:
        assert active_batcher.get() is batcher
        assert active_target is None


@pytest.mark.asyncio
async def test_batching_context_starts_and_stops_live_display(
    batcher: Batcher,
    reset_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that async context starts and stops live display listeners."""

    class DummyDisplay:
        """Simple display stub."""

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
    context = BatchingContext(
        batcher=batcher,
        live_display=True,
    )

    with patch.object(target=batcher, attribute="close", new_callable=AsyncMock):
        async with context:
            assert dummy_display.started is True
        assert dummy_display.stopped is True


def test_batching_context_sync_stops_live_display_without_loop(
    batcher: Batcher,
    reset_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test sync context stops display when no event loop is running."""

    class DummyDisplay:
        """Simple display stub."""

        def __init__(self) -> None:
            self.stopped = False

        def start(self) -> None:
            return None

        def stop(self) -> None:
            self.stopped = True

        def on_event(self, event: dict[str, t.Any]) -> None:
            del event

    dummy_display = DummyDisplay()
    monkeypatch.setattr("batchling.context_display.BatcherRichDisplay", lambda: dummy_display)
    monkeypatch.setattr(
        "batchling.context_display.should_enable_live_display", lambda **_kwargs: True
    )

    context = BatchingContext(
        batcher=batcher,
        live_display=True,
    )

    with warnings.catch_warnings(record=True):
        warnings.simplefilter(action="always")
        with context:
            pass

    assert dummy_display.stopped is True


@pytest.mark.asyncio
async def test_batching_context_uses_polling_progress_fallback_when_auto_disabled(
    batcher: Batcher,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test live-display fallback logs progress at poll time when Rich is disabled."""
    monkeypatch.setattr(
        "batchling.context_display.should_enable_live_display", lambda **_kwargs: False
    )
    context = BatchingContext(
        batcher=batcher,
        live_display=True,
    )

    caplog.set_level(level=logging.INFO, logger="batchling.context_display")

    with patch.object(target=batcher, attribute="close", new_callable=AsyncMock):
        async with context:
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


@pytest.mark.asyncio
async def test_batching_context_skips_live_display_in_dry_run(
    reset_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test dry-run mode does not start live display listeners."""

    class DummyDisplay:
        """Simple display stub."""

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

    batcher = Batcher(
        batch_size=1,
        batch_window_seconds=1.0,
        dry_run=True,
        cache=False,
    )
    context = BatchingContext(
        batcher=batcher,
        live_display=True,
    )

    with patch.object(target=batcher, attribute="close", new_callable=AsyncMock):
        async with context:
            pass
    assert dummy_display.started is False


@pytest.mark.asyncio
async def test_batching_context_prints_dry_run_report_when_live_display_disabled(
    reset_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test dry-run report prints on context exit even when live display is disabled."""

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

    batcher = Batcher(
        batch_size=1,
        batch_window_seconds=1.0,
        dry_run=True,
        cache=False,
    )
    context = BatchingContext(
        batcher=batcher,
        live_display=False,
    )

    async with context:
        result = await batcher.submit(
            client_type="httpx",
            method="POST",
            url="api.openai.com",
            endpoint="/v1/chat/completions",
            provider=OpenAIProvider(),
            body=b'{"model":"model-a","messages":[]}',
        )

    assert isinstance(result, _DryRunAbortSignal)

    assert dry_run_display.print_calls == 1


@pytest.mark.asyncio
async def test_batching_context_suppresses_dry_run_early_exit(
    batcher: Batcher,
    reset_context: None,
) -> None:
    """Test async context suppresses DryRunEarlyExit for clean user output."""
    context = BatchingContext(batcher=batcher)

    did_raise = False
    try:
        async with context:
            raise DryRunEarlyExit(
                source=BatcherEventSource.DRY_RUN,
                provider="openai",
                endpoint="/v1/chat/completions",
                model="model-a",
                batch_id="dryrun-test",
                custom_id="custom-1",
            )
    except DryRunEarlyExit:
        did_raise = True

    assert did_raise is False


@pytest.mark.asyncio
async def test_batching_context_does_not_suppress_non_dry_run_exceptions(
    batcher: Batcher,
    reset_context: None,
) -> None:
    """Test async context does not suppress runtime exceptions."""
    context = BatchingContext(batcher=batcher)

    with pytest.raises(RuntimeError, match="boom"):
        async with context:
            raise RuntimeError("boom")


def test_batching_context_sync_suppresses_dry_run_early_exit(
    batcher: Batcher,
    reset_context: None,
) -> None:
    """Test sync context suppresses DryRunEarlyExit."""
    context = BatchingContext(batcher=batcher)

    did_raise = False
    with warnings.catch_warnings():
        warnings.simplefilter(action="ignore")
        try:
            with context:
                raise DryRunEarlyExit(
                    source=BatcherEventSource.DRY_RUN,
                    provider="openai",
                    endpoint="/v1/chat/completions",
                    model="model-a",
                    batch_id="dryrun-test",
                    custom_id="custom-1",
                )
        except DryRunEarlyExit:
            did_raise = True

    assert did_raise is False
