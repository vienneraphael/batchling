"""
Core engine containing the async batch watching mechanism.
The mechanism acts as a batch queue that collects requests and submits them as batches.
Should support multiple queues for multiple providers/endpoints/models called in same job.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import typing as t
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import structlog

from batchling.cache import CacheEntry, RequestCacheStore
from batchling.providers import BaseProvider
from batchling.providers.base import PollSnapshot, ProviderRequestSpec

log = structlog.get_logger(__name__)
QueueKey = tuple[str, str, str]
ResumedBatchKey = tuple[str, str, str]
CACHE_RETENTION_SECONDS = 30 * 24 * 60 * 60


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
    request_hash: str


@dataclass
class _ActiveBatch:
    """A batch that has been submitted and is being polled."""

    batch_id: str
    output_file_id: str
    error_file_id: str
    requests: dict[str, _PendingRequest]  # custom_id -> request


@dataclass
class _ResumedPendingRequest:
    """A pending request attached to a resumed provider batch."""

    request_hash: str
    future: asyncio.Future[t.Any]


@dataclass
class _ResumedBatch:
    """Resumed cache-hit batch polled by batch ID."""

    provider: BaseProvider
    base_url: str
    api_headers: dict[str, str]
    requests_by_custom_id: dict[str, list[_ResumedPendingRequest]]


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
        cache: bool = True,
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
        cache : bool
            If ``True``, enable persistent request cache lookups.
        """
        self._batch_size = batch_size
        self._batch_window_seconds = batch_window_seconds
        self._dry_run = dry_run
        self._cache_enabled = cache
        self._cache_write_enabled = cache and not dry_run

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
        self._batch_tasks: set[asyncio.Task[None]] = set()
        self._resumed_poll_tasks: set[asyncio.Task[None]] = set()
        self._resumed_batches: dict[ResumedBatchKey, _ResumedBatch] = {}
        self._resumed_lock = asyncio.Lock()

        self._cache_store: RequestCacheStore | None = None
        if self._cache_enabled:
            try:
                self._cache_store = RequestCacheStore()
            except OSError as error:
                self._cache_enabled = False
                self._cache_write_enabled = False
                log.warning(
                    event="Failed to initialize cache store; disabling cache",
                    error=str(object=error),
                )

        log.debug(
            event="Initialized Batcher",
            batch_size=batch_size,
            batch_window_seconds=batch_window_seconds,
            batch_poll_interval_seconds=batch_poll_interval_seconds,
            dry_run=dry_run,
            cache_enabled=self._cache_enabled,
            cache_write_enabled=self._cache_write_enabled,
            cache_path=(
                self._cache_store.path.as_posix() if self._cache_store is not None else None
            ),
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

    @staticmethod
    def _resolve_host(*, url: str) -> str:
        """
        Resolve request host from raw URL-like input.

        Parameters
        ----------
        url : str
            Raw URL or host string.

        Returns
        -------
        str
            Lowercased host.
        """
        parsed_url = urlparse(url=url)
        if parsed_url.hostname:
            return str(object=parsed_url.hostname).lower()
        return str(object=url).split(sep="/")[0].lower()

    def _build_request_hash(
        self,
        *,
        queue_key: QueueKey,
        host: str,
        body: bytes | None,
    ) -> str:
        """
        Build deterministic request fingerprint for cache lookup.

        Parameters
        ----------
        queue_key : QueueKey
            Queue key ``(provider, endpoint, model)``.
        host : str
            Provider host.
        body : bytes | None
            Intercepted request body.

        Returns
        -------
        str
            SHA-256 fingerprint for cache identity.
        """
        if body is None:
            raise ValueError("Batch request JSON body is required for cache fingerprinting")
        provider_name, endpoint, model_name = queue_key
        payload = json.loads(s=body.decode(encoding="utf-8"))
        canonical_payload = json.dumps(
            obj={
                "provider": provider_name,
                "endpoint": endpoint,
                "model": model_name,
                "host": host,
                "body": payload,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical_payload.encode(encoding="utf-8")).hexdigest()

    def _lookup_cache_entry(
        self,
        *,
        request_hash: str,
    ) -> CacheEntry | None:
        """
        Fetch cache metadata for a request hash.

        Parameters
        ----------
        request_hash : str
            Request fingerprint.

        Returns
        -------
        CacheEntry | None
            Cache entry when available.
        """
        if not self._cache_enabled or self._cache_store is None:
            return None
        return self._cache_store.get_by_hash(request_hash=request_hash)

    async def _try_submit_from_cache(
        self,
        *,
        queue_key: QueueKey,
        endpoint: str,
        provider: BaseProvider,
        host: str,
        headers: dict[str, str] | None,
        request_hash: str,
        request_params: dict[str, t.Any],
        future: asyncio.Future[t.Any],
    ) -> CacheEntry | None:
        """
        Try resolving an intercepted request via cache-hit routing.

        Parameters
        ----------
        queue_key : QueueKey
            Queue partition key.
        endpoint : str
            Request endpoint.
        provider : BaseProvider
            Provider adapter for this request.
        host : str
            Provider host.
        headers : dict[str, str] | None
            Request headers.
        request_hash : str
            Request fingerprint.
        request_params : dict[str, typing.Any]
            Captured request parameters.
        future : asyncio.Future[typing.Any]
            Future to resolve.

        Returns
        -------
        CacheEntry | None
            Matched cache entry when routed through cache.
        """
        cache_entry = self._lookup_cache_entry(request_hash=request_hash)
        provider_name, _, model_name = queue_key
        if cache_entry is None:
            log.debug(
                event="Cache miss for intercepted request",
                provider=provider_name,
                endpoint=endpoint,
                model=model_name,
                host=host,
            )
            return None

        log.info(
            event="Cache hit for intercepted request",
            provider=provider_name,
            endpoint=endpoint,
            model=model_name,
            host=host,
            batch_id=cache_entry.batch_id,
            custom_id=cache_entry.custom_id,
        )
        if self._dry_run:
            dry_run_request = _PendingRequest(
                custom_id=cache_entry.custom_id,
                queue_key=queue_key,
                params=request_params,
                provider=provider,
                future=future,
                request_hash=request_hash,
            )
            future.set_result(
                self._build_dry_run_response(
                    request=dry_run_request,
                    cache_hit=True,
                )
            )
            return cache_entry

        await self._attach_cached_request(
            provider=provider,
            host=host,
            headers=headers,
            cache_entry=cache_entry,
            request_hash=request_hash,
            future=future,
        )
        return cache_entry

    async def _enqueue_pending_request(
        self,
        *,
        request: _PendingRequest,
    ) -> None:
        """
        Enqueue pending request and trigger submission when thresholds are reached.

        Parameters
        ----------
        request : _PendingRequest
            Request to queue.
        """
        queue_key = request.queue_key
        provider_name, queue_endpoint, model_name = queue_key
        queue_name = self._format_queue_key(queue_key=queue_key)
        requests_to_submit: list[_PendingRequest] = []

        log.debug(
            event="Queued request for batch",
            provider=provider_name,
            queue_endpoint=queue_endpoint,
            model=model_name,
            queue_key=queue_name,
            custom_id=request.custom_id,
            client_type=request.params["client_type"],
            method=request.params["method"],
            url=request.params["url"],
            endpoint=request.params["endpoint"],
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
        host = self._resolve_host(url=url)
        request_params = {
            "client_type": client_type,
            "method": method,
            "url": url,
            "endpoint": endpoint,
            "headers": headers,
            "body": body,
            **kwargs,
        }
        try:
            queue_key = self._build_queue_key(provider=provider, endpoint=endpoint, body=body)
            request_hash = self._build_request_hash(queue_key=queue_key, host=host, body=body)
        except (ValueError, json.JSONDecodeError) as error:
            log.error(
                event="Failed to resolve request key",
                provider=provider_name,
                custom_id=custom_id,
                error=str(object=error),
            )
            future.set_exception(error)
            return await future

        cache_entry = await self._try_submit_from_cache(
            queue_key=queue_key,
            endpoint=endpoint,
            provider=provider,
            host=host,
            headers=headers,
            request_hash=request_hash,
            request_params=request_params,
            future=future,
        )
        if cache_entry is not None:
            try:
                return await future
            except asyncio.CancelledError:
                raise
            except Exception as error:
                log.info(
                    event="Cache route failed; falling back to fresh batch submission",
                    provider=provider_name,
                    endpoint=endpoint,
                    model=queue_key[2],
                    host=host,
                    batch_id=cache_entry.batch_id,
                    custom_id=cache_entry.custom_id,
                    error=str(object=error),
                )
                _ = self._invalidate_cache_hashes(request_hashes=[request_hash])
                custom_id = str(object=uuid.uuid4())
                future = loop.create_future()

        request = _PendingRequest(
            custom_id=custom_id,
            queue_key=queue_key,
            params=request_params,
            provider=provider,
            future=future,
            request_hash=request_hash,
        )
        await self._enqueue_pending_request(request=request)
        return await future

    @staticmethod
    def _build_resumed_batch_key(
        *,
        provider_name: str,
        host: str,
        batch_id: str,
    ) -> ResumedBatchKey:
        """
        Build key used for resumed cache-hit polling tasks.

        Parameters
        ----------
        provider_name : str
            Provider adapter name.
        host : str
            Provider host.
        batch_id : str
            Provider batch ID.

        Returns
        -------
        ResumedBatchKey
            Tuple key for resumed polling.
        """
        return provider_name, host, batch_id

    async def _attach_cached_request(
        self,
        *,
        provider: BaseProvider,
        host: str,
        headers: dict[str, str] | None,
        cache_entry: CacheEntry,
        request_hash: str,
        future: asyncio.Future[t.Any],
    ) -> None:
        """
        Attach a cache-hit request to a resumed polling task.

        Parameters
        ----------
        provider : BaseProvider
            Provider adapter.
        host : str
            Provider host.
        headers : dict[str, str] | None
            Intercepted request headers.
        cache_entry : CacheEntry
            Cache row metadata.
        request_hash : str
            Request fingerprint.
        future : asyncio.Future[typing.Any]
            Future to resolve when results are available.
        """
        resume_key = self._build_resumed_batch_key(
            provider_name=provider.name,
            host=host,
            batch_id=cache_entry.batch_id,
        )
        should_start_poller = False
        async with self._resumed_lock:
            resumed_batch = self._resumed_batches.get(resume_key)
            if resumed_batch is None:
                resume_context = provider.build_resume_context(
                    host=host,
                    headers=headers,
                )
                resumed_batch = _ResumedBatch(
                    provider=provider,
                    base_url=resume_context.base_url,
                    api_headers=resume_context.api_headers,
                    requests_by_custom_id={},
                )
                self._resumed_batches[resume_key] = resumed_batch
                should_start_poller = True

            resumed_batch.requests_by_custom_id.setdefault(cache_entry.custom_id, []).append(
                _ResumedPendingRequest(
                    request_hash=request_hash,
                    future=future,
                )
            )

        if should_start_poller:
            task = asyncio.create_task(
                coro=self._poll_cached_batch(resume_key=resume_key),
                name=f"cache_resume_poll_{provider.name}_{cache_entry.batch_id}",
            )
            self._resumed_poll_tasks.add(task)
            task.add_done_callback(self._on_resumed_poll_task_done)

    def _on_submission_task_done(self, task: asyncio.Task[None]) -> None:
        """
        Cleanup callback for background batch submission tasks.

        Parameters
        ----------
        task : asyncio.Task[None]
            Completed task.
        """
        self._batch_tasks.discard(task)
        try:
            _ = task.exception()
        except asyncio.CancelledError:
            pass

    def _on_resumed_poll_task_done(self, task: asyncio.Task[None]) -> None:
        """
        Cleanup callback for background resumed poll tasks.

        Parameters
        ----------
        task : asyncio.Task[None]
            Completed task.
        """
        self._resumed_poll_tasks.discard(task)
        try:
            _ = task.exception()
        except asyncio.CancelledError:
            pass

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
        task = asyncio.create_task(
            coro=self._process_batch(queue_key=queue_key, requests=requests),
            name=f"batch_submit_{queue_name}_{uuid.uuid4()}",
        )
        self._batch_tasks.add(task)
        task.add_done_callback(self._on_submission_task_done)

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

    def _write_cache_entries(
        self,
        *,
        queue_key: QueueKey,
        requests: list[_PendingRequest],
        batch_id: str,
    ) -> None:
        """
        Persist submitted batch request metadata to cache.

        Parameters
        ----------
        queue_key : QueueKey
            Queue key associated with submitted requests.
        requests : list[_PendingRequest]
            Submitted requests.
        batch_id : str
            Provider batch identifier.
        """
        if not self._cache_write_enabled or self._cache_store is None or not requests:
            return

        provider_name, endpoint, model_name = queue_key
        created_at = time.time()
        entries = [
            CacheEntry(
                request_hash=request.request_hash,
                provider=provider_name,
                endpoint=endpoint,
                model=model_name,
                host=self._resolve_host(url=str(request.params["url"])),
                batch_id=batch_id,
                custom_id=request.custom_id,
                created_at=created_at,
            )
            for request in requests
        ]
        affected_rows = self._cache_store.upsert_many(entries=entries)
        min_created_at = created_at - CACHE_RETENTION_SECONDS
        deleted_rows = self._cache_store.delete_older_than(min_created_at=min_created_at)
        log.debug(
            event="Persisted submitted batch requests to cache",
            provider=provider_name,
            endpoint=endpoint,
            model=model_name,
            batch_id=batch_id,
            upserted_rows=affected_rows,
            cleaned_rows=deleted_rows,
            retention_seconds=CACHE_RETENTION_SECONDS,
        )

    def _invalidate_cache_hashes(self, *, request_hashes: t.Iterable[str]) -> int:
        """
        Remove cache rows by request hash.

        Parameters
        ----------
        request_hashes : typing.Iterable[str]
            Hashes to delete.

        Returns
        -------
        int
            Number of removed rows.
        """
        if not self._cache_write_enabled or self._cache_store is None:
            return 0
        deleted_rows = self._cache_store.delete_by_hashes(request_hashes=request_hashes)
        if deleted_rows:
            log.info(
                event="Invalidated stale cache rows",
                deleted_rows=deleted_rows,
            )
        return deleted_rows

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
                )
                self._active_batches.append(active_batch)
                for req in requests:
                    if not req.future.done():
                        req.future.set_result(
                            self._build_dry_run_response(
                                request=req,
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
            self._write_cache_entries(
                queue_key=queue_key,
                requests=requests,
                batch_id=batch_submission.batch_id,
            )

            active_batch = _ActiveBatch(
                batch_id=batch_submission.batch_id,
                output_file_id="",
                error_file_id="",
                requests={req.custom_id: req for req in requests},
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
        except asyncio.CancelledError:
            log.debug(
                event="Batch processing task cancelled",
                provider=provider_name,
                queue_endpoint=queue_endpoint,
                model=model_name,
                queue_key=queue_name,
            )
            raise
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
        cache_hit: bool = False,
    ) -> httpx.Response:
        """
        Build a synthetic response for dry-run batch mode.

        Parameters
        ----------
        request : _PendingRequest
            Pending request metadata.
        cache_hit : bool, optional
            Whether this dry-run response came from a cache lookup.

        Returns
        -------
        httpx.Response
            Synthetic successful response.
        """
        return httpx.Response(
            status_code=200,
            headers={
                "x-batchling-dry-run": "1",
                "x-batchling-cache-hit": "1" if cache_hit else "0",
            },
            json={
                "dry_run": True,
                "custom_id": request.custom_id,
                "provider": request.provider.name,
                "status": "simulated",
                "cache_hit": cache_hit,
            },
        )

    async def _poll_batch_once(
        self,
        *,
        provider: BaseProvider,
        base_url: str,
        api_headers: dict[str, str],
        batch_id: str,
    ) -> PollSnapshot:
        """
        Execute one provider batch poll request.

        Parameters
        ----------
        provider : BaseProvider
            Provider adapter.
        base_url : str
            Provider base URL.
        api_headers : dict[str, str]
            Provider API headers.
        batch_id : str
            Provider batch ID.

        Returns
        -------
        PollSnapshot
            Snapshot of provider batch status and output/error file IDs.
        """
        poll_request_spec = provider.build_poll_request_spec(
            base_url=base_url,
            api_headers=api_headers,
            batch_id=batch_id,
        )
        response = await self._execute_provider_request(
            base_url=base_url,
            request_spec=poll_request_spec,
        )
        payload = response.json()
        return await provider.parse_poll_response(payload=payload)

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
            poll_snapshot = await self._poll_batch_once(
                provider=provider,
                base_url=base_url,
                api_headers=api_headers,
                batch_id=active_batch.batch_id,
            )
            active_batch.output_file_id = poll_snapshot.output_file_id
            active_batch.error_file_id = poll_snapshot.error_file_id
            log.debug(
                event="Batch poll tick",
                provider=provider.name,
                batch_id=active_batch.batch_id,
                status=poll_snapshot.status,
                has_output_file=bool(poll_snapshot.output_file_id),
                has_error_file=bool(poll_snapshot.error_file_id),
            )

            if poll_snapshot.status in provider.batch_terminal_states:
                log.info(
                    event="Batch reached terminal state",
                    provider=provider.name,
                    batch_id=active_batch.batch_id,
                    status=poll_snapshot.status,
                )
                await self._resolve_batch_results(
                    base_url=base_url,
                    api_headers=api_headers,
                    provider=provider,
                    active_batch=active_batch,
                )
                return

            await asyncio.sleep(delay=self._poll_interval_seconds)

    async def _poll_cached_batch(
        self,
        *,
        resume_key: ResumedBatchKey,
    ) -> None:
        """
        Poll an existing provider batch for cache-hit requests.

        Parameters
        ----------
        resume_key : ResumedBatchKey
            Resumed batch key ``(provider, host, batch_id)``.
        """
        async with self._resumed_lock:
            resumed_batch = self._resumed_batches.get(resume_key)
        if resumed_batch is None:
            return

        provider = resumed_batch.provider
        _, host, batch_id = resume_key
        try:
            log.info(
                event="Polling resumed cached batch",
                provider=provider.name,
                host=host,
                batch_id=batch_id,
            )
            while True:
                poll_snapshot = await self._poll_batch_once(
                    provider=provider,
                    base_url=resumed_batch.base_url,
                    api_headers=resumed_batch.api_headers,
                    batch_id=batch_id,
                )
                log.debug(
                    event="Resumed batch poll tick",
                    provider=provider.name,
                    batch_id=batch_id,
                    status=poll_snapshot.status,
                    has_output_file=bool(poll_snapshot.output_file_id),
                    has_error_file=bool(poll_snapshot.error_file_id),
                )
                if poll_snapshot.status in provider.batch_terminal_states:
                    await self._resolve_cached_batch_results(
                        resume_key=resume_key,
                        output_file_id=poll_snapshot.output_file_id,
                        error_file_id=poll_snapshot.error_file_id,
                    )
                    return

                await asyncio.sleep(delay=self._poll_interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await self._fail_resumed_batch_requests(
                resume_key=resume_key,
                error=error,
                invalidate_cache=True,
            )
        finally:
            async with self._resumed_lock:
                self._resumed_batches.pop(resume_key, None)

    async def _resolve_cached_batch_results(
        self,
        *,
        resume_key: ResumedBatchKey,
        output_file_id: str,
        error_file_id: str,
    ) -> None:
        """
        Resolve pending cache-hit futures from provider batch outputs.

        Parameters
        ----------
        resume_key : ResumedBatchKey
            Resumed batch key.
        output_file_id : str
            Provider output file ID.
        error_file_id : str
            Provider error file ID.
        """
        async with self._resumed_lock:
            resumed_batch = self._resumed_batches.get(resume_key)
        if resumed_batch is None:
            return

        _, _, batch_id = resume_key
        provider = resumed_batch.provider
        file_id = output_file_id or error_file_id
        try:
            results_request_spec = provider.build_results_request_spec(
                base_url=resumed_batch.base_url,
                api_headers=resumed_batch.api_headers,
                file_id=file_id,
                batch_id=batch_id,
            )
        except ValueError as error:
            await self._fail_resumed_batch_requests(
                resume_key=resume_key,
                error=RuntimeError(str(object=error)),
                invalidate_cache=True,
            )
            return

        content = await self._download_batch_content(
            base_url=resumed_batch.base_url,
            request_spec=results_request_spec,
        )
        responses_by_custom_id = provider.decode_results_content(
            batch_id=batch_id,
            content=content,
        )

        missing_hashes: set[str] = set()
        async with self._resumed_lock:
            current_batch = self._resumed_batches.get(resume_key)
        if current_batch is None:
            return

        for custom_id, pending_requests in current_batch.requests_by_custom_id.items():
            resolved_response = responses_by_custom_id.get(custom_id)
            if resolved_response is None:
                for pending in pending_requests:
                    missing_hashes.add(pending.request_hash)
                    if not pending.future.done():
                        pending.future.set_exception(
                            RuntimeError(f"Missing results for request '{custom_id}'")
                        )
                continue

            for pending in pending_requests:
                if not pending.future.done():
                    pending.future.set_result(resolved_response)

        if missing_hashes:
            _ = self._invalidate_cache_hashes(request_hashes=missing_hashes)

    async def _fail_resumed_batch_requests(
        self,
        *,
        resume_key: ResumedBatchKey,
        error: Exception,
        invalidate_cache: bool,
    ) -> None:
        """
        Fail unresolved requests attached to a resumed cache-hit batch.

        Parameters
        ----------
        resume_key : ResumedBatchKey
            Resumed batch key.
        error : Exception
            Exception to attach to unresolved futures.
        invalidate_cache : bool
            Whether to remove involved cache hashes.
        """
        async with self._resumed_lock:
            resumed_batch = self._resumed_batches.get(resume_key)
        if resumed_batch is None:
            return

        request_hashes: set[str] = set()
        for pending_list in resumed_batch.requests_by_custom_id.values():
            for pending in pending_list:
                request_hashes.add(pending.request_hash)
                if not pending.future.done():
                    pending.future.set_exception(error)

        if invalidate_cache and request_hashes:
            _ = self._invalidate_cache_hashes(request_hashes=request_hashes)

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
            results_request_spec = provider.build_results_request_spec(
                base_url=base_url,
                api_headers=api_headers,
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
            results_path=results_request_spec.path,
        )
        content = await self._download_batch_content(
            base_url=base_url,
            request_spec=results_request_spec,
        )
        responses_by_custom_id = provider.decode_results_content(
            batch_id=active_batch.batch_id,
            content=content,
        )
        seen = set(responses_by_custom_id.keys())
        for custom_id, resolved_response in responses_by_custom_id.items():
            seen.add(custom_id)
            pending = active_batch.requests.get(custom_id)
            if pending and not pending.future.done():
                pending.future.set_result(resolved_response)
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
        request_spec: ProviderRequestSpec,
    ) -> str:
        """
        Download batch results file content.

        Parameters
        ----------
        base_url : str
            Provider base URL.
        request_spec : ProviderRequestSpec
            Provider request specification for result download.

        Returns
        -------
        str
            Raw JSONL content.
        """
        response = await self._execute_provider_request(
            base_url=base_url,
            request_spec=request_spec,
        )
        return response.text

    async def _execute_provider_request(
        self,
        *,
        base_url: str,
        request_spec: ProviderRequestSpec,
    ) -> httpx.Response:
        """
        Execute a provider request using the shared batcher client factory.

        Parameters
        ----------
        base_url : str
            Provider base URL.
        request_spec : ProviderRequestSpec
            Provider request metadata.

        Returns
        -------
        httpx.Response
            Provider HTTP response.
        """
        request_kwargs: dict[str, t.Any] = {
            "url": f"{base_url}{request_spec.path}",
            "headers": request_spec.headers,
        }
        if request_spec.json_body is not None:
            request_kwargs["json"] = request_spec.json_body
        if request_spec.content is not None:
            request_kwargs["content"] = request_spec.content
        if request_spec.files is not None:
            request_kwargs["files"] = request_spec.files
        if request_spec.data is not None:
            request_kwargs["data"] = request_spec.data

        async with self._client_factory() as client:
            response = await client.request(
                method=request_spec.method,
                **request_kwargs,
            )
            response.raise_for_status()
            return response

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
