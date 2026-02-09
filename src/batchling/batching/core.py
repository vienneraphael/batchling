"""
Core engine containing the async batch watching mechanism.
The mechanism acts as a batch queue that collects requests and submits them as batches.
Should support multiple queues for multiple providers/models called in same job.
"""

from __future__ import annotations

import asyncio
import json
import time
import typing as t
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import structlog

from batchling.batching.providers import BaseProvider, get_provider_for_url
from batchling.utils.api import get_default_api_key_from_provider

log = structlog.get_logger(__name__)


@dataclass
class _PendingRequest:
    # FIXME: _PendingRequest can use a generic type to match any request from:
    # - http.client.HTTPSConnection.request
    # - aiohttp.ClientSession._request
    # - httpx.AsyncClient.request
    """A request waiting to be batched."""

    custom_id: str
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
    The pending queue is partitioned by provider to apply batching limits per provider.
    """

    def __init__(
        self,
        batch_size: int = 10,
        batch_window_seconds: float = 2.0,
    ):
        """
        Initialize the batcher.

        Parameters
        ----------
        batch_size : int
            Submit a batch when this many requests are queued for a provider.
        batch_window_seconds : float
            Submit a provider batch after this many seconds, even if size not reached.
        """
        self._batch_size = batch_size
        self._batch_window_seconds = batch_window_seconds

        # Request collection
        self._pending_by_provider: dict[str, list[_PendingRequest]] = {}
        self._pending_lock = asyncio.Lock()
        self._window_tasks: dict[str, asyncio.Task[None]] = {}

        # Active batches being tracked
        self._active_batches: list[_ActiveBatch] = []
        self._client_factory: t.Callable[[], httpx.AsyncClient] = lambda: httpx.AsyncClient(
            timeout=30.0
        )
        self._poll_interval_seconds = 2.0

        log.debug(
            event="Initialized Batcher",
            batch_size=batch_size,
            batch_window_seconds=batch_window_seconds,
        )

    async def submit(
        self,
        client_type: str,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: t.Any = None,
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
        headers : dict[str, str] | None, optional
            HTTP headers for the request.
        body : typing.Any, optional
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

        provider = get_provider_for_url(url=url)
        if provider is None:
            raise ValueError(f"No provider registered for URL: {url}")

        custom_id = str(object=uuid.uuid4())

        request = _PendingRequest(
            custom_id=custom_id,
            params={
                "client_type": client_type,
                "method": method,
                "url": url,
                "headers": headers,
                "body": body,
                **kwargs,
            },
            provider=provider,
            future=future,
        )

        provider_name = provider.name
        requests_to_submit: list[_PendingRequest] = []

        log.debug(
            event="Queued request for batch",
            provider=provider_name,
            custom_id=custom_id,
            client_type=client_type,
            method=method,
            url=url,
        )

        async with self._pending_lock:
            queue = self._pending_by_provider.setdefault(provider_name, [])
            queue.append(request)
            pending_count = len(queue)
            log.debug(
                event="Pending queue updated",
                provider=provider_name,
                pending_count=pending_count,
            )

            # Start window timer if this is the first request
            if pending_count == 1:
                log.debug(
                    event="Starting batch window timer",
                    provider=provider_name,
                    batch_window_seconds=self._batch_window_seconds,
                )
                self._window_tasks[provider_name] = asyncio.create_task(
                    coro=self._window_timer(provider_name=provider_name),
                    name=f"batch_window_timer_{provider_name}",
                )

            # Check if we've hit the size threshold
            if pending_count >= self._batch_size:
                log.debug(
                    event="Batch size reached",
                    provider=provider_name,
                    batch_size=self._batch_size,
                )
                requests_to_submit = self._drain_provider_queue(
                    provider_name=provider_name,
                )

        if requests_to_submit:
            await self._submit_requests(
                provider_name=provider_name,
                requests=requests_to_submit,
            )

        return await future

    async def _window_timer(self, *, provider_name: str) -> None:
        """
        Trigger provider batch submission after the window elapses.

        Parameters
        ----------
        provider_name : str
            Provider key for the pending queue.
        """
        try:
            log.debug(
                event="Window timer started",
                provider=provider_name,
                batch_window_seconds=self._batch_window_seconds,
            )
            await asyncio.sleep(delay=self._batch_window_seconds)
            requests_to_submit: list[_PendingRequest] = []
            async with self._pending_lock:
                queue = self._pending_by_provider.get(provider_name, [])
                if queue:
                    log.debug(
                        event="Batch window elapsed, submitting batch",
                        provider=provider_name,
                    )
                    requests_to_submit = self._drain_provider_queue(
                        provider_name=provider_name,
                    )
                else:
                    log.debug(
                        event="Batch window elapsed with empty queue",
                        provider=provider_name,
                    )
            if requests_to_submit:
                await self._submit_requests(
                    provider_name=provider_name,
                    requests=requests_to_submit,
                )
        except asyncio.CancelledError:
            log.debug(event="Window timer cancelled", provider=provider_name)
            raise
        except Exception as e:
            log.error(
                event="Window timer error",
                provider=provider_name,
                error=str(object=e),
            )
            await self._fail_pending_provider_requests(
                provider_name=provider_name,
                error=e,
            )
            raise

    async def _submit_requests(
        self,
        *,
        provider_name: str,
        requests: list[_PendingRequest],
    ) -> None:
        """
        Submit a provider-specific batch in the background.

        Parameters
        ----------
        provider_name : str
            Provider key associated with the batch.
        requests : list[_PendingRequest]
            Requests to submit in a single provider batch.
        """
        if not requests:
            return

        log.info(
            event="Submitting batch",
            provider=provider_name,
            request_count=len(requests),
        )
        asyncio.create_task(
            coro=self._process_batch(requests=requests),
            name=f"batch_submit_{provider_name}_{uuid.uuid4()}",
        )

    def _drain_provider_queue(self, *, provider_name: str) -> list[_PendingRequest]:
        """
        Drain pending requests for a provider and cancel its window timer.

        Parameters
        ----------
        provider_name : str
            Provider key for the pending queue.

        Returns
        -------
        list[_PendingRequest]
            Drained requests for that provider.
        """
        current_task = asyncio.current_task()
        window_task = self._window_tasks.get(provider_name)
        if window_task and not window_task.done() and window_task is not current_task:
            window_task.cancel()
        self._window_tasks.pop(provider_name, None)

        requests = self._pending_by_provider.pop(provider_name, [])
        log.debug(
            event="Drained provider queue",
            provider=provider_name,
            drained_count=len(requests),
        )
        return requests

    async def _fail_pending_provider_requests(
        self,
        *,
        provider_name: str,
        error: Exception,
    ) -> None:
        """
        Fail all pending requests for a provider.

        Parameters
        ----------
        provider_name : str
            Provider key for the pending queue.
        error : Exception
            Exception to attach to pending futures.
        """
        async with self._pending_lock:
            queue = self._pending_by_provider.get(provider_name, [])
            for req in queue:
                if not req.future.done():
                    req.future.set_exception(error)

    def _extract_body(self, *, params: dict[str, t.Any]) -> t.Any:
        """
        Extract a request body from hook parameters.

        Parameters
        ----------
        params : dict[str, typing.Any]
            Hook parameters captured from the HTTP request.

        Returns
        -------
        typing.Any
            Extracted body value, if any.
        """
        if params.get("json") is not None:
            return params["json"]
        for key in ("body", "content", "data"):
            if params.get(key) is not None:
                return params[key]
        return None

    def _normalize_body(self, *, body: t.Any) -> t.Any:
        """
        Normalize a request body for JSONL serialization.

        Parameters
        ----------
        body : typing.Any
            Raw request body.

        Returns
        -------
        typing.Any
            Normalized request body.
        """
        if body is None:
            return None
        if isinstance(body, (dict, list)):
            return body
        if isinstance(body, (bytes, bytearray)):
            try:
                decoded = body.decode(encoding="utf-8")
            except Exception:
                return body.decode(encoding="utf-8", errors="replace")
            return self._maybe_parse_json(value=decoded)
        if isinstance(body, str):
            return self._maybe_parse_json(value=body)
        return body

    def _maybe_parse_json(self, *, value: str) -> t.Any:
        """
        Parse a JSON string if possible.

        Parameters
        ----------
        value : str
            String payload.

        Returns
        -------
        typing.Any
            Parsed JSON or original string.
        """
        try:
            return json.loads(s=value)
        except Exception:
            return value

    def _normalize_headers(
        self,
        *,
        headers: dict[str, str] | None,
    ) -> dict[str, str]:
        """
        Normalize headers into a mutable mapping.

        Parameters
        ----------
        headers : dict[str, str] | None
            Input headers.

        Returns
        -------
        dict[str, str]
            Normalized headers.
        """
        return dict(headers) if headers else {}

    def _build_api_headers(
        self,
        *,
        provider: BaseProvider,
        headers: dict[str, str],
    ) -> dict[str, str]:
        """
        Build API headers for provider batch requests.

        Parameters
        ----------
        provider : BaseProvider
            Provider adapter.
        headers : dict[str, str]
            Original request headers.

        Returns
        -------
        dict[str, str]
            Headers to use for provider API calls.
        """
        api_headers: dict[str, str] = {}
        for key, value in headers.items():
            lower_key = key.lower()
            if lower_key == "authorization":
                api_headers["Authorization"] = value
            elif lower_key.startswith("openai-"):
                api_headers[key] = value

        if "Authorization" not in api_headers:
            api_key = get_default_api_key_from_provider(provider=provider.name)
            api_headers["Authorization"] = f"Bearer {api_key}"
        return api_headers

    def _build_internal_headers(self, *, headers: dict[str, str]) -> dict[str, str]:
        """
        Add internal bypass headers for provider API calls.

        Parameters
        ----------
        headers : dict[str, str]
            Base headers.

        Returns
        -------
        dict[str, str]
            Headers with internal bypass marker.
        """
        return {**headers, "x-batchling-internal": "1"}

    def _extract_base_and_endpoint(
        self,
        *,
        provider: BaseProvider,
        url: str,
    ) -> tuple[str, str]:
        """
        Extract base URL and endpoint path for a provider request.

        Parameters
        ----------
        provider : BaseProvider
            Provider adapter.
        url : str
            Original request URL.

        Returns
        -------
        tuple[str, str]
            Base URL and endpoint path.
        """
        parsed = urlparse(url=url)
        if parsed.scheme and parsed.netloc:
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            endpoint = provider.normalize_url(url=url)
            return base_url, endpoint

        if provider.hostnames:
            base_url = f"https://{provider.hostnames[0]}"
            endpoint = provider.normalize_url(url=url)
            return base_url, endpoint

        raise ValueError(f"Unable to determine base URL for request: {url}")

    async def _process_batch(self, *, requests: list[_PendingRequest]) -> None:
        """
        Upload, create, and poll a provider batch for results.

        Parameters
        ----------
        requests : list[_PendingRequest]
            Requests to submit in the batch.
        """
        provider = requests[0].provider
        if provider.name != "openai":
            error = NotImplementedError(
                f"Batch submission not implemented for provider: {provider.name}"
            )
            for req in requests:
                if not req.future.done():
                    req.future.set_exception(error)
            return

        try:
            log.info(
                event="Processing batch",
                provider=provider.name,
                request_count=len(requests),
            )
            base_url, endpoint = self._extract_base_and_endpoint(
                provider=provider,
                url=requests[0].params["url"],
            )
            log.debug(
                event="Resolved batch target",
                provider=provider.name,
                base_url=base_url,
                endpoint=endpoint,
            )
            api_headers = self._build_api_headers(
                provider=provider,
                headers=self._normalize_headers(
                    headers=requests[0].params.get("headers"),
                ),
            )
            api_headers = self._build_internal_headers(headers=api_headers)

            jsonl_lines = self._build_jsonl_lines(
                provider=provider,
                requests=requests,
            )
            log.debug(
                event="Built JSONL lines",
                provider=provider.name,
                request_count=len(jsonl_lines),
            )
            file_id = await self._upload_batch_file(
                base_url=base_url,
                api_headers=api_headers,
                jsonl_lines=jsonl_lines,
            )
            log.info(
                event="Uploaded batch file",
                provider=provider.name,
                file_id=file_id,
                request_count=len(jsonl_lines),
            )
            batch_id = await self._create_batch_job(
                base_url=base_url,
                api_headers=api_headers,
                file_id=file_id,
                endpoint=endpoint,
            )
            log.info(
                event="Created batch job",
                provider=provider.name,
                batch_id=batch_id,
                file_id=file_id,
            )

            active_batch = _ActiveBatch(
                batch_id=batch_id,
                output_file_id="",
                error_file_id="",
                requests={req.custom_id: req for req in requests},
                created_at=time.time(),
            )
            self._active_batches.append(active_batch)
            log.debug(
                event="Tracking active batch",
                provider=provider.name,
                batch_id=batch_id,
                active_batch_count=len(self._active_batches),
            )

            await self._poll_batch(
                base_url=base_url,
                api_headers=api_headers,
                provider=provider,
                active_batch=active_batch,
            )
        except Exception as e:
            log.error(event="Batch submission failed", error=str(object=e))
            for req in requests:
                if not req.future.done():
                    req.future.set_exception(e)

    def _build_jsonl_lines(
        self,
        *,
        provider: BaseProvider,
        requests: list[_PendingRequest],
    ) -> list[dict[str, t.Any]]:
        """
        Build JSONL request lines for a provider batch.

        Parameters
        ----------
        provider : BaseProvider
            Provider adapter.
        requests : list[_PendingRequest]
            Pending requests to serialize.

        Returns
        -------
        list[dict[str, typing.Any]]
            JSONL-ready line objects.
        """
        jsonl_lines: list[dict[str, t.Any]] = []
        for req in requests:
            body = self._normalize_body(
                body=self._extract_body(params=req.params),
            )
            line: dict[str, t.Any] = {
                "custom_id": req.custom_id,
                "method": req.params["method"],
                "url": provider.normalize_url(url=req.params["url"]),
            }
            if body is not None:
                line["body"] = body
            jsonl_lines.append(line)
        return jsonl_lines

    async def _upload_batch_file(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        jsonl_lines: list[dict[str, t.Any]],
    ) -> str:
        """
        Upload a JSONL batch input file.

        Parameters
        ----------
        base_url : str
            Provider base URL.
        api_headers : dict[str, str]
            Provider API headers.
        jsonl_lines : list[dict[str, typing.Any]]
            JSONL line payloads.

        Returns
        -------
        str
            Provider file ID.
        """
        file_content = "\n".join(json.dumps(obj=line) for line in jsonl_lines).encode(
            encoding="utf-8"
        )
        files = {
            "file": ("batch.jsonl", file_content, "application/jsonl"),
        }

        log.debug(
            event="Uploading batch file",
            base_url=base_url,
            line_count=len(jsonl_lines),
            bytes=len(file_content),
        )
        async with self._client_factory() as client:
            response = await client.post(
                url=f"{base_url}/v1/files",
                headers=api_headers,
                files=files,
                data={"purpose": "batch"},
            )
            response.raise_for_status()
            payload = response.json()
        return payload["id"]

    async def _create_batch_job(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        file_id: str,
        endpoint: str,
    ) -> str:
        """
        Create a provider batch job.

        Parameters
        ----------
        base_url : str
            Provider base URL.
        api_headers : dict[str, str]
            Provider API headers.
        file_id : str
            Uploaded batch file ID.
        endpoint : str
            Provider endpoint path.

        Returns
        -------
        str
            Provider batch ID.
        """
        async with self._client_factory() as client:
            response = await client.post(
                url=f"{base_url}/v1/batches",
                headers=api_headers,
                json={
                    "input_file_id": file_id,
                    "endpoint": endpoint,
                    "completion_window": "24h",
                    "metadata": {"description": "batchling runtime batch"},
                },
            )
            response.raise_for_status()
            payload = response.json()
        log.debug(
            event="Batch job created",
            base_url=base_url,
            batch_id=payload.get("id"),
            input_file_id=file_id,
        )
        return payload["id"]

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
        terminal_states = {"completed", "failed", "cancelled", "expired"}
        log.info(
            event="Polling batch",
            provider=provider.name,
            batch_id=active_batch.batch_id,
            poll_interval_seconds=self._poll_interval_seconds,
        )
        while True:
            async with self._client_factory() as client:
                response = await client.get(
                    url=f"{base_url}/v1/batches/{active_batch.batch_id}",
                    headers=api_headers,
                )
                response.raise_for_status()
                payload = response.json()

            status = payload.get("status", "created")
            active_batch.output_file_id = payload.get("output_file_id") or ""
            active_batch.error_file_id = payload.get("error_file_id") or ""
            log.debug(
                event="Batch poll tick",
                provider=provider.name,
                batch_id=active_batch.batch_id,
                status=status,
                has_output_file=bool(active_batch.output_file_id),
                has_error_file=bool(active_batch.error_file_id),
            )

            if status in terminal_states:
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
        file_id = self._resolve_batch_file_id(active_batch=active_batch)
        if file_id is None:
            log.error(
                event="Batch resolved without output file",
                provider=provider.name,
                batch_id=active_batch.batch_id,
            )
            return

        log.info(
            event="Downloading batch results",
            provider=provider.name,
            batch_id=active_batch.batch_id,
            file_id=file_id,
        )
        content = await self._download_batch_content(
            base_url=base_url,
            api_headers=api_headers,
            file_id=file_id,
        )
        seen = self._apply_batch_results(
            provider=provider,
            active_batch=active_batch,
            content=content,
        )
        log.info(
            event="Applied batch results",
            provider=provider.name,
            batch_id=active_batch.batch_id,
            resolved_count=len(seen),
            request_count=len(active_batch.requests),
        )
        self._fail_missing_results(active_batch=active_batch, seen=seen)

    def _resolve_batch_file_id(self, *, active_batch: _ActiveBatch) -> str | None:
        """
        Resolve the output or error file ID for a batch.

        Parameters
        ----------
        active_batch : _ActiveBatch
            Active batch metadata.

        Returns
        -------
        str | None
            File identifier or ``None`` if unavailable.
        """
        file_id = active_batch.output_file_id or active_batch.error_file_id
        if not file_id:
            error = RuntimeError("Batch completed without output or error file")
            for req in active_batch.requests.values():
                if not req.future.done():
                    req.future.set_exception(error)
            return None
        return file_id

    async def _download_batch_content(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        file_id: str,
    ) -> str:
        """
        Download batch results file content.

        Parameters
        ----------
        base_url : str
            Provider base URL.
        api_headers : dict[str, str]
            Provider API headers.
        file_id : str
            Provider file ID.

        Returns
        -------
        str
            Raw JSONL content.
        """
        async with self._client_factory() as client:
            response = await client.get(
                url=f"{base_url}/v1/files/{file_id}/content",
                headers=api_headers,
            )
            response.raise_for_status()
            log.debug(
                event="Downloaded batch content",
                file_id=file_id,
                status_code=response.status_code,
            )
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
            custom_id = result_item.get("custom_id")
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
        for provider_name, window_task in list(self._window_tasks.items()):
            if window_task and not window_task.done():
                window_task.cancel()
                try:
                    await window_task
                except asyncio.CancelledError:
                    pass
        self._window_tasks.clear()

        pending_batches: list[tuple[str, list[_PendingRequest]]] = []
        async with self._pending_lock:
            for provider_name in list(self._pending_by_provider.keys()):
                requests = self._drain_provider_queue(provider_name=provider_name)
                if requests:
                    pending_batches.append((provider_name, requests))

        for provider_name, requests in pending_batches:
            log.info(
                event="Submitting final batch on close",
                provider=provider_name,
                request_count=len(requests),
            )
            await self._submit_requests(
                provider_name=provider_name,
                requests=requests,
            )

        log.debug(event="Batcher closed")
