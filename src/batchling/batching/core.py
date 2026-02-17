"""
Core engine containing the async batch watching mechanism.
The mechanism acts as a batch queue that collects requests and submits them as batches.
Should support multiple queues for multiple providers/endpoints/models called in same job.
"""

from __future__ import annotations

import asyncio
import json
import time
import typing as t
import uuid
from dataclasses import dataclass

import httpx
import structlog

from batchling.batching.providers import BaseProvider

log = structlog.get_logger(__name__)
QueueKey = tuple[str, str, str]


@dataclass
class _PendingRequest:
    # FIXME: _PendingRequest can use a generic type to match any request from:
    # - http.client.HTTPSConnection.request
    # - aiohttp.ClientSession._request
    # - httpx.AsyncClient.request
    """A request waiting to be batched."""

    custom_id: str
    queue_key: QueueKey
    params: dict[str, t.Any]
    provider: BaseProvider
    future: asyncio.Future[t.Any]


@dataclass
class _ActiveBatch:
    """A batch that has been submitted and is being polled."""

    batch_id: str
    output_file_id: str
    error_file_id: str
    requests: dict[str, _PendingRequest]  # custom_id -> request
    created_at: float
    last_offset: int = 0  # Track offset for partial result streaming


class Batcher:
    """
    Manage queues, timers, and the accumulate-submit-poll lifecycle.

    Collect requests over a time window or until a size threshold, then submit
    them as batches. Batches are sent when either:
    - The provider queue reaches ``batch_size``, OR
    - The provider ``batch_window_seconds`` time elapses

    Notes
    -----
    The pending queue is partitioned by ``(provider, endpoint, model)`` to
    apply batching limits per queue scope.
    """

    def __init__(
        self,
        batch_size: int = 50,
        batch_window_seconds: float = 2.0,
        batch_poll_interval_seconds: float = 10.0,
        dry_run: bool = False,
    ):
        """
        Initialize the batcher.

        Parameters
        ----------
        batch_size : int
            Submit a batch when this many requests are queued for a provider.
        batch_window_seconds : float
            Submit a provider batch after this many seconds, even if size not reached.
        batch_poll_interval_seconds : float
            Poll active batches every this many seconds.
        dry_run : bool
            If ``True``, simulate provider batch resolution without provider I/O.
        """
        self._batch_size = batch_size
        self._batch_window_seconds = batch_window_seconds
        self._dry_run = dry_run

        # Request collection
        self._pending_by_provider: dict[QueueKey, list[_PendingRequest]] = {}
        self._pending_lock = asyncio.Lock()
        self._window_tasks: dict[QueueKey, asyncio.Task[None]] = {}

        # Active batches being tracked
        self._active_batches: list[_ActiveBatch] = []
        self._client_factory: t.Callable[[], httpx.AsyncClient] = lambda: httpx.AsyncClient(
            timeout=30.0
        )
        self._poll_interval_seconds = batch_poll_interval_seconds

        log.debug(
            event="Initialized Batcher",
            batch_size=batch_size,
            batch_window_seconds=batch_window_seconds,
            batch_poll_interval_seconds=batch_poll_interval_seconds,
            dry_run=dry_run,
        )

    @staticmethod
    def _format_queue_key(*, queue_key: QueueKey) -> str:
        """
        Format a queue key for readability in logs.

        Parameters
        ----------
        queue_key : QueueKey
            Queue identifier as ``(provider_name, endpoint, model_name)``.

        Returns
        -------
        str
            Queue key formatted as ``provider:endpoint:model``.
        """
        provider_name, endpoint, model_name = queue_key
        return f"{provider_name}:{endpoint}:{model_name}"

    def _build_queue_key(
        self, *, provider: BaseProvider, endpoint: str, body: bytes | None
    ) -> QueueKey:
        """
        Compute queue partition key for a pending request.

        Parameters
        ----------
        provider : BaseProvider
            Provider responsible for the request.
        endpoint : str
            Request endpoint used for queue partitioning.
        body : bytes | None
            Request body used for model extraction.

        Returns
        -------
        QueueKey
            Queue key tuple containing provider, endpoint, and model.
        """
        model = provider.extract_model_name(
            endpoint=endpoint,
            body=body,
        )
        return provider.name, endpoint, model

    async def submit(
        self,
        client_type: str,
        method: str,
        url: str,
        endpoint: str,
        provider: BaseProvider,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        **kwargs: t.Any,
    ) -> t.Any:
        """
        Queue a request for batching and return its resolved response.

        Parameters
        ----------
        client_type : str
            Type of client (e.g., ``"httpx"`` or ``"aiohttp"``).
        method : str
            HTTP method (e.g., ``"GET"`` or ``"POST"``).
        url : str
            Request URL.
        endpoint : str
            Request endpoint.
        provider : BaseProvider
            Provider for this request.
        headers : dict[str, str] | None, optional
            HTTP headers for the request.
        body : bytes, optional
            Raw request body.
        **kwargs : typing.Any
            Additional request parameters forwarded from the hook.

        Returns
        -------
        typing.Any
            Provider-decoded response.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[t.Any] = loop.create_future()

        custom_id = str(object=uuid.uuid4())

        provider_name = provider.name
        try:
            queue_key = self._build_queue_key(provider=provider, endpoint=endpoint, body=body)
        except ValueError as error:
            log.error(
                event="Failed to resolve queue key",
                provider=provider_name,
                custom_id=custom_id,
                error=str(object=error),
            )
            future.set_exception(error)
            return await future

        request = _PendingRequest(
            custom_id=custom_id,
            queue_key=queue_key,
            params={
                "client_type": client_type,
                "method": method,
                "url": url,
                "endpoint": endpoint,
                "headers": headers,
                "body": body,
                **kwargs,
            },
            provider=provider,
            future=future,
        )

        queue_name = self._format_queue_key(queue_key=queue_key)
        _, queue_endpoint, model_name = queue_key
        requests_to_submit: list[_PendingRequest] = []

        log.debug(
            event="Queued request for batch",
            provider=provider_name,
            queue_endpoint=queue_endpoint,
            model=model_name,
            queue_key=queue_name,
            custom_id=custom_id,
            client_type=client_type,
            method=method,
            url=url,
            endpoint=endpoint,
        )

        async with self._pending_lock:
            queue = self._pending_by_provider.setdefault(queue_key, [])
            queue.append(request)
            pending_count = len(queue)
            log.debug(
                event="Pending queue updated",
                provider=provider_name,
                queue_endpoint=queue_endpoint,
                model=model_name,
                queue_key=queue_name,
                pending_count=pending_count,
            )

            # Start window timer if this is the first request
            if pending_count == 1:
                log.debug(
                    event="Starting batch window timer",
                    provider=provider_name,
                    queue_endpoint=queue_endpoint,
                    model=model_name,
                    queue_key=queue_name,
                    batch_window_seconds=self._batch_window_seconds,
                )
                self._window_tasks[queue_key] = asyncio.create_task(
                    coro=self._window_timer(queue_key=queue_key),
                    name=f"batch_window_timer_{queue_name}",
                )

            # Check if we've hit the size threshold
            if pending_count >= self._batch_size:
                log.debug(
                    event="Batch size reached",
                    provider=provider_name,
                    queue_endpoint=queue_endpoint,
                    model=model_name,
                    queue_key=queue_name,
                    batch_size=self._batch_size,
                )
                requests_to_submit = self._drain_provider_queue(
                    queue_key=queue_key,
                )

        if requests_to_submit:
            await self._submit_requests(
                queue_key=queue_key,
                requests=requests_to_submit,
            )

        return await future

    async def _window_timer(self, *, queue_key: QueueKey) -> None:
        """
        Trigger provider batch submission after the window elapses.

        Parameters
        ----------
        queue_key : QueueKey
            Queue key for the pending queue.
        """
        provider_name, queue_endpoint, model_name = queue_key
        queue_name = self._format_queue_key(queue_key=queue_key)
        try:
            log.debug(
                event="Window timer started",
                provider=provider_name,
                queue_endpoint=queue_endpoint,
                model=model_name,
                queue_key=queue_name,
                batch_window_seconds=self._batch_window_seconds,
            )
            await asyncio.sleep(delay=self._batch_window_seconds)
            requests_to_submit: list[_PendingRequest] = []
            async with self._pending_lock:
                queue = self._pending_by_provider.get(queue_key, [])
                if queue:
                    log.debug(
                        event="Batch window elapsed, submitting batch",
                        provider=provider_name,
                        queue_endpoint=queue_endpoint,
                        model=model_name,
                        queue_key=queue_name,
                    )
                    requests_to_submit = self._drain_provider_queue(
                        queue_key=queue_key,
                    )
                else:
                    log.debug(
                        event="Batch window elapsed with empty queue",
                        provider=provider_name,
                        queue_endpoint=queue_endpoint,
                        model=model_name,
                        queue_key=queue_name,
                    )
            if requests_to_submit:
                await self._submit_requests(
                    queue_key=queue_key,
                    requests=requests_to_submit,
                )
        except asyncio.CancelledError:
            log.debug(
                event="Window timer cancelled",
                provider=provider_name,
                queue_endpoint=queue_endpoint,
                model=model_name,
                queue_key=queue_name,
            )
            raise
        except Exception as e:
            log.error(
                event="Window timer error",
                provider=provider_name,
                queue_endpoint=queue_endpoint,
                model=model_name,
                queue_key=queue_name,
                error=str(object=e),
            )
            await self._fail_pending_provider_requests(
                queue_key=queue_key,
                error=e,
            )
            raise

    async def _submit_requests(
        self,
        *,
        queue_key: QueueKey,
        requests: list[_PendingRequest],
    ) -> None:
        """
        Submit a provider-specific batch in the background.

        Parameters
        ----------
        queue_key : QueueKey
            Queue key associated with the batch.
        requests : list[_PendingRequest]
            Requests to submit in a single provider batch.
        """
        if not requests:
            return
        provider_name, queue_endpoint, model_name = queue_key
        queue_name = self._format_queue_key(queue_key=queue_key)

        log.info(
            event="Submitting batch",
            provider=provider_name,
            queue_endpoint=queue_endpoint,
            model=model_name,
            queue_key=queue_name,
            request_count=len(requests),
        )
        asyncio.create_task(
            coro=self._process_batch(queue_key=queue_key, requests=requests),
            name=f"batch_submit_{queue_name}_{uuid.uuid4()}",
        )

    def _drain_provider_queue(self, *, queue_key: QueueKey) -> list[_PendingRequest]:
        """
        Drain pending requests for a provider and cancel its window timer.

        Parameters
        ----------
        queue_key : QueueKey
            Queue key for the pending queue.

        Returns
        -------
        list[_PendingRequest]
            Drained requests for that provider.
        """
        current_task = asyncio.current_task()
        provider_name, queue_endpoint, model_name = queue_key
        queue_name = self._format_queue_key(queue_key=queue_key)
        window_task = self._window_tasks.get(queue_key)
        if window_task and not window_task.done() and window_task is not current_task:
            window_task.cancel()
        self._window_tasks.pop(queue_key, None)

        requests = self._pending_by_provider.pop(queue_key, [])
        log.debug(
            event="Drained provider queue",
            provider=provider_name,
            queue_endpoint=queue_endpoint,
            model=model_name,
            queue_key=queue_name,
            drained_count=len(requests),
        )
        return requests

    async def _fail_pending_provider_requests(
        self,
        *,
        queue_key: QueueKey,
        error: Exception,
    ) -> None:
        """
        Fail all pending requests for a provider.

        Parameters
        ----------
        queue_key : QueueKey
            Queue key for the pending queue.
        error : Exception
            Exception to attach to pending futures.
        """
        async with self._pending_lock:
            queue = self._pending_by_provider.get(queue_key, [])
            for req in queue:
                if not req.future.done():
                    req.future.set_exception(error)

    async def _process_batch(
        self,
        *,
        queue_key: QueueKey,
        requests: list[_PendingRequest],
    ) -> None:
        """
        Submit a provider batch and start polling lifecycle.

        Parameters
        ----------
        queue_key : QueueKey
            Queue key associated with the drained request batch.
        requests : list[_PendingRequest]
            Requests to submit in the batch.
        """
        if not requests:
            raise ValueError("Cannot process an empty request batch")

        provider = requests[0].provider
        queue_name = self._format_queue_key(queue_key=queue_key)
        provider_name, queue_endpoint, model_name = queue_key
        try:
            if self._dry_run:
                dry_run_batch_id = f"dryrun-{uuid.uuid4()}"
                active_batch = _ActiveBatch(
                    batch_id=dry_run_batch_id,
                    output_file_id="",
                    error_file_id="",
                    requests={req.custom_id: req for req in requests},
                    created_at=time.time(),
                )
                self._active_batches.append(active_batch)
                for req in requests:
                    if not req.future.done():
                        req.future.set_result(
                            self._build_dry_run_response(
                                request=req,
                                provider_name=provider.name,
                            )
                        )
                log.info(
                    event="Dry-run batch resolved",
                    provider=provider.name,
                    queue_endpoint=queue_endpoint,
                    model=model_name,
                    queue_key=queue_name,
                    batch_id=dry_run_batch_id,
                    request_count=len(requests),
                )
                return

            log.info(
                event="Processing batch",
                provider=provider.name,
                queue_endpoint=queue_endpoint,
                model=model_name,
                queue_key=queue_name,
                request_count=len(requests),
            )
            batch_submission = await provider.process_batch(
                requests=requests,
                client_factory=self._client_factory,
                queue_key=queue_key,
            )
            log.debug(
                event="Provider batch submitted",
                provider=provider.name,
                queue_endpoint=queue_endpoint,
                model=model_name,
                queue_key=queue_name,
                batch_id=batch_submission.batch_id,
                base_url=batch_submission.base_url,
            )

            active_batch = _ActiveBatch(
                batch_id=batch_submission.batch_id,
                output_file_id="",
                error_file_id="",
                requests={req.custom_id: req for req in requests},
                created_at=time.time(),
            )
            self._active_batches.append(active_batch)
            log.debug(
                event="Tracking active batch",
                provider=provider.name,
                queue_endpoint=queue_endpoint,
                model=model_name,
                queue_key=queue_name,
                batch_id=batch_submission.batch_id,
                active_batch_count=len(self._active_batches),
            )

            await self._poll_batch(
                base_url=batch_submission.base_url,
                api_headers=batch_submission.api_headers,
                provider=provider,
                active_batch=active_batch,
            )
        except Exception as e:
            log.error(
                event="Batch submission failed",
                provider=provider_name,
                queue_endpoint=queue_endpoint,
                model=model_name,
                queue_key=queue_name,
                error=str(object=e),
            )
            for req in requests:
                if not req.future.done():
                    req.future.set_exception(e)

    def _build_dry_run_response(
        self,
        *,
        request: _PendingRequest,
        provider_name: str,
    ) -> httpx.Response:
        """
        Build a synthetic response for dry-run batch mode.

        Parameters
        ----------
        request : _PendingRequest
            Pending request metadata.
        provider_name : str
            Provider name for observability.

        Returns
        -------
        httpx.Response
            Synthetic successful response.
        """
        return httpx.Response(
            status_code=200,
            headers={"x-batchling-dry-run": "1"},
            json={
                "dry_run": True,
                "custom_id": request.custom_id,
                "provider": provider_name,
                "status": "simulated",
            },
        )

    async def _poll_batch(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        provider: BaseProvider,
        active_batch: _ActiveBatch,
    ) -> None:
        """
        Poll a provider batch until completion and resolve results.

        Parameters
        ----------
        base_url : str
            Provider base URL.
        api_headers : dict[str, str]
            Provider API headers.
        provider : BaseProvider
            Provider adapter.
        active_batch : _ActiveBatch
            Active batch metadata.
        """
        log.info(
            event="Polling batch",
            provider=provider.name,
            batch_id=active_batch.batch_id,
            poll_interval_seconds=self._poll_interval_seconds,
        )
        while True:
            poll_path = provider.build_batch_poll_path(batch_id=active_batch.batch_id)
            async with self._client_factory() as client:
                response = await client.get(
                    url=f"{base_url}{poll_path}",
                    headers=api_headers,
                )
                response.raise_for_status()
                payload = response.json()
            # FIXME: fit into a data validation model
            status = provider.extract_batch_status(payload=payload)
            active_batch.output_file_id = await provider.get_output_file_id_from_poll_response(
                payload=payload,
            )
            active_batch.error_file_id = payload.get(provider.error_file_field_name) or ""
            log.debug(
                event="Batch poll tick",
                provider=provider.name,
                batch_id=active_batch.batch_id,
                status=status,
                has_output_file=bool(active_batch.output_file_id),
                has_error_file=bool(active_batch.error_file_id),
            )

            if status in provider.batch_terminal_states:
                log.info(
                    event="Batch reached terminal state",
                    provider=provider.name,
                    batch_id=active_batch.batch_id,
                    status=status,
                )
                await self._resolve_batch_results(
                    base_url=base_url,
                    api_headers=api_headers,
                    provider=provider,
                    active_batch=active_batch,
                )
                return

            await asyncio.sleep(delay=self._poll_interval_seconds)

    async def _resolve_batch_results(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        provider: BaseProvider,
        active_batch: _ActiveBatch,
    ) -> None:
        """
        Download batch results and resolve pending futures.

        Parameters
        ----------
        base_url : str
            Provider base URL.
        api_headers : dict[str, str]
            Provider API headers.
        provider : BaseProvider
            Provider adapter.
        active_batch : _ActiveBatch
            Active batch metadata.
        """
        file_id = active_batch.output_file_id or active_batch.error_file_id
        try:
            results_path = provider.build_batch_results_path(
                file_id=file_id,
                batch_id=active_batch.batch_id,
            )
        except ValueError as error:
            log.error(
                event="Batch resolved without output file",
                provider=provider.name,
                batch_id=active_batch.batch_id,
                error=str(object=error),
            )
            runtime_error = RuntimeError(str(object=error))
            for req in active_batch.requests.values():
                if not req.future.done():
                    req.future.set_exception(runtime_error)
            return

        log.info(
            event="Downloading batch results",
            provider=provider.name,
            batch_id=active_batch.batch_id,
            file_id=file_id,
            results_path=results_path,
        )
        content = await self._download_batch_content(
            base_url=base_url,
            api_headers=api_headers,
            results_path=results_path,
        )
        seen = self._apply_batch_results(
            provider=provider,
            active_batch=active_batch,
            content=content,
        )
        log.info(
            event="Mapped batch results to output requests",
            provider=provider.name,
            batch_id=active_batch.batch_id,
            resolved_count=len(seen),
            request_count=len(active_batch.requests),
        )
        self._fail_missing_results(active_batch=active_batch, seen=seen)

    async def _download_batch_content(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        results_path: str,
    ) -> str:
        """
        Download batch results file content.

        Parameters
        ----------
        base_url : str
            Provider base URL.
        api_headers : dict[str, str]
            Provider API headers.
        results_path : str
            Provider results endpoint path.

        Returns
        -------
        str
            Raw JSONL content.
        """
        async with self._client_factory() as client:
            response = await client.get(
                url=f"{base_url}{results_path}",
                headers=api_headers,
            )
            response.raise_for_status()
            return response.text

    def _apply_batch_results(
        self,
        *,
        provider: BaseProvider,
        active_batch: _ActiveBatch,
        content: str,
    ) -> set[str]:
        """
        Apply batch results to pending futures.

        Parameters
        ----------
        provider : BaseProvider
            Provider adapter.
        active_batch : _ActiveBatch
            Active batch metadata.
        content : str
            Raw JSONL content.

        Returns
        -------
        set[str]
            Custom IDs that were resolved.
        """
        seen: set[str] = set()
        for line in content.splitlines():
            if not line.strip():
                continue
            result_item = json.loads(s=line)
            custom_id = result_item.get(
                provider.custom_id_field_name,
            )
            if custom_id is None:
                log.debug(
                    event="Batch result missing custom_id",
                    provider=provider.name,
                    batch_id=active_batch.batch_id,
                )
                continue
            seen.add(custom_id)
            pending = active_batch.requests.get(custom_id)
            if pending and not pending.future.done():
                pending.future.set_result(
                    provider.from_batch_result(result_item=result_item),
                )
        return seen

    def _fail_missing_results(
        self,
        *,
        active_batch: _ActiveBatch,
        seen: set[str],
    ) -> None:
        """
        Fail futures that did not appear in the results.

        Parameters
        ----------
        active_batch : _ActiveBatch
            Active batch metadata.
        seen : set[str]
            Custom IDs observed in the results.
        """
        missing = set(active_batch.requests.keys()) - seen
        if not missing:
            return
        log.error(
            event="Missing batch results",
            batch_id=active_batch.batch_id,
            missing_count=len(missing),
        )
        error = RuntimeError(f"Missing results for {len(missing)} request(s)")
        for custom_id in missing:
            pending = active_batch.requests.get(custom_id)
            if pending and not pending.future.done():
                pending.future.set_exception(error)

    async def close(self) -> None:
        """
        Cleanup resources and flush pending requests.

        Notes
        -----
        Pending requests are submitted per provider before closing.
        """
        for queue_key, window_task in list(self._window_tasks.items()):
            provider_name, queue_endpoint, model_name = queue_key
            queue_name = self._format_queue_key(queue_key=queue_key)
            if window_task and not window_task.done():
                window_task.cancel()
                try:
                    await window_task
                except asyncio.CancelledError:
                    log.debug(
                        event="Window timer cancelled during close",
                        provider=provider_name,
                        queue_endpoint=queue_endpoint,
                        model=model_name,
                        queue_key=queue_name,
                    )
                    pass
        self._window_tasks.clear()

        pending_batches: list[tuple[QueueKey, list[_PendingRequest]]] = []
        async with self._pending_lock:
            for queue_key in list(self._pending_by_provider.keys()):
                requests = self._drain_provider_queue(queue_key=queue_key)
                if requests:
                    pending_batches.append((queue_key, requests))

        for queue_key, requests in pending_batches:
            provider_name, queue_endpoint, model_name = queue_key
            queue_name = self._format_queue_key(queue_key=queue_key)
            log.info(
                event="Submitting final batch on close",
                provider=provider_name,
                queue_endpoint=queue_endpoint,
                model=model_name,
                queue_key=queue_name,
                request_count=len(requests),
            )
            await self._submit_requests(
                queue_key=queue_key,
                requests=requests,
            )

        log.debug(event="Batcher closed")
