from __future__ import annotations

import json
import typing as t
from abc import ABC
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class BatchSubmission:
    """
    Metadata returned after a provider submits a batch job.

    Parameters
    ----------
    base_url : str
        Provider base URL used for polling.
    api_headers : dict[str, str]
        Provider API headers used for polling and result download.
    batch_id : str
        Provider batch identifier.
    """

    base_url: str
    api_headers: dict[str, str]
    batch_id: str


class PendingRequestLike(t.Protocol):
    """
    Minimal shape required by providers to serialize batch input.

    Attributes
    ----------
    custom_id : str
        Request identifier in the provider batch file.
    params : dict[str, typing.Any]
        Request parameters captured by the hook.
    """

    custom_id: str
    params: dict[str, t.Any]


class BatchPayload(t.TypedDict):
    """
    Minimal shape required by providers to serialize batch input.
    """

    input_file_id: str
    endpoint: str
    completion_window: t.NotRequired[str]
    metadata: t.NotRequired[dict[str, str]]


class BatchTerminalStatesLike(t.Protocol):
    SUCCESS: str
    FAILED: str
    CANCELLED: str
    EXPIRED: str


class BaseProvider(ABC):
    """
    Standard interface for mapping HTTP requests to/from provider Batch APIs.

    Providers implement:
    - process_batch: create a provider batch job from pending requests
    - from_batch_result: parse a JSONL result line back into an httpx.Response
    """

    name: str = "base"
    hostnames: tuple[str, ...] = ()
    batch_method: str = "POST"
    batchable_endpoints: tuple[str, ...] = ()
    file_upload_endpoint: str
    batch_endpoint: str
    batch_requires_homogeneous_model: bool = False
    batch_payload_type: type[BatchPayload]
    batch_terminal_states: type[BatchTerminalStatesLike]

    def _normalize_base_url(self, *, url: str) -> str:
        """
        Normalize provider base URL into an absolute HTTPS URL.

        Parameters
        ----------
        url : str
            Base URL or hostname from pending request params.

        Returns
        -------
        str
            Absolute base URL without trailing slash.
        """
        stripped = url.strip().rstrip("/")
        if not stripped:
            raise ValueError("OpenAI base URL cannot be empty")

        parsed = urlparse(url=stripped)
        if parsed.scheme:
            return stripped

        return f"https://{stripped}"

    def matches_url(self, hostname: str) -> bool:
        """
        Check whether a URL belongs to this provider by hostname.

        Parameters
        ----------
        hostname : str
            Candidate request hostname.

        Returns
        -------
        bool
            ``True`` if the hostname matches this provider.
        """
        is_match = bool(hostname) and hostname.endswith(self.hostnames)
        log.debug(
            event="Provider URL match evaluated",
            provider=self.name,
            input_hostname=hostname,
            parsed_hostname=hostname,
            matched=is_match,
        )
        return is_match

    def is_batchable_request(self, *, method: str, hostname: str, path: str) -> bool:
        """
        Check whether an HTTP request should be routed into batching.

        Parameters
        ----------
        method : str
            HTTP method for the request.
        hostname : str
            Candidate request hostname.
        path : str
            Candidate request path.

        Returns
        -------
        bool
            ``True`` if this request is explicitly batchable for the provider.
        """
        normalized_method = method.upper()
        if not self.matches_url(hostname=hostname):
            return False
        method_ok = normalized_method == self.batch_method
        endpoint_ok = path in self.batchable_endpoints
        is_batchable = method_ok and endpoint_ok
        log.debug(
            event="Provider batchable endpoint evaluated",
            provider=self.name,
            method=normalized_method,
            path=path,
            expected_method=self.batch_method,
            method_ok=method_ok,
            endpoint_ok=endpoint_ok,
            matched=is_batchable,
            configured_endpoints=self.batchable_endpoints,
        )
        return is_batchable

    def build_internal_headers(self, *, headers: dict[str, str]) -> dict[str, str]:
        """
        Add internal bypass headers to provider API requests.

        Parameters
        ----------
        headers : dict[str, str]
            Provider API headers.

        Returns
        -------
        dict[str, str]
            Headers including internal bypass marker.
        """
        internal_headers = {**headers, "x-batchling-internal": "1"}
        log.debug(
            event="Built internal provider headers",
            provider=self.name,
            input_header_count=len(headers),
            output_header_count=len(internal_headers),
            output_header_keys=list(internal_headers.keys()),
        )
        return internal_headers

    def build_jsonl_lines(
        self,
        *,
        requests: t.Sequence[PendingRequestLike],
    ) -> list[dict[str, t.Any]]:
        """
        Build provider batch-file JSONL lines.

        Parameters
        ----------
        requests : list[PendingRequestLike]
            Pending requests to serialize.

        Returns
        -------
        list[dict[str, typing.Any]]
            JSONL-ready request lines.
        """
        return [
            {
                "custom_id": request.custom_id,
                "method": request.params["method"],
                "url": request.params["endpoint"],
                "body": json.loads(
                    s=request.params["body"].decode(encoding="utf-8"),
                ),
            }
            for request in requests
        ]

    def encode_body(self, *, body: dict[str, t.Any]) -> tuple[bytes, dict[str, str]]:
        """
        Encode response payloads into bytes and content headers.

        Parameters
        ----------
        body : dict[str, typing.Any]
            Response payload.

        Returns
        -------
        tuple[bytes, dict[str, str]]
            Encoded bytes and any content-type headers.
        """
        encoded = json.dumps(obj=body).encode(encoding="utf-8")
        return encoded, {"content-type": "application/json"}

    def build_api_headers(self, *, headers: dict[str, str]) -> dict[str, str]:
        """
        Extract bearer token from request headers.

        Parameters
        ----------
        headers : dict[str, str]
            Original request headers.

        Returns
        -------
        dict[str, str]
            Request headers with bearer token extracted.
        """
        api_headers: dict[str, str] = {}
        for key, value in headers.items():
            lower_key = key.lower()
            if lower_key == "authorization":
                api_headers["Authorization"] = value
            elif lower_key.startswith(f"{self.name}-"):
                api_headers[key] = value
        return api_headers

    async def _upload_batch_file(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        jsonl_lines: list[dict[str, t.Any]],
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> str:
        """
        Upload OpenAI batch input file.

        Parameters
        ----------
        base_url : str
            OpenAI base URL.
        api_headers : dict[str, str]
            OpenAI API headers.
        jsonl_lines : list[dict[str, typing.Any]]
            JSONL line payloads.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.

        Returns
        -------
        str
            OpenAI file ID.
        """
        file_content = "\n".join(json.dumps(obj=line) for line in jsonl_lines).encode(
            encoding="utf-8"
        )
        files = {
            "file": ("batch.jsonl", file_content, "application/jsonl"),
        }

        log.debug(
            event="Uploading batch file",
            provider=self.name,
            base_url=base_url,
            line_count=len(jsonl_lines),
            bytes=len(file_content),
            first_custom_id=jsonl_lines[0]["custom_id"] if jsonl_lines else None,
        )

        async with client_factory() as client:
            response = await client.post(
                url=f"{base_url}{self.file_upload_endpoint}",
                headers=api_headers,
                files=files,
                data={"purpose": "batch"},
            )
            response.raise_for_status()
            payload = response.json()
        return payload["id"]

    async def _build_batch_payload(
        self,
        *,
        file_id: str,
        endpoint: str,
        queue_key: tuple[str, str | None],
    ) -> t.Mapping[str, t.Any]:
        """
        Build a batch payload for the provider.
        """
        del queue_key
        return self.batch_payload_type(
            input_file_id=file_id,
            endpoint=endpoint,
            completion_window="24h",
            metadata={"description": "batchling runtime batch"},
        )

    async def _create_batch_job(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        file_id: str,
        endpoint: str,
        queue_key: tuple[str, str | None],
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> str:
        """
        Create an OpenAI batch job.

        Parameters
        ----------
        base_url : str
            OpenAI base URL.
        api_headers : dict[str, str]
            OpenAI API headers.
        file_id : str
            Uploaded input file ID.
        endpoint : str
            Endpoint path included in the batch job.
        queue_key : tuple[str, str | None]
            Queue key associated with the current batch.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.

        Returns
        -------
        str
            OpenAI batch ID.
        """
        payload = await self._build_batch_payload(
            file_id=file_id,
            endpoint=endpoint,
            queue_key=queue_key,
        )
        log.debug(
            "Sending batch request",
            url=f"{base_url}{self.batch_endpoint}",
            headers={k: "***" for k in api_headers.keys()},
            payload=payload,
        )
        async with client_factory() as client:
            response = await client.post(
                url=f"{base_url}{self.batch_endpoint}", headers=api_headers, json=payload
            )
            response.raise_for_status()
            payload = response.json()
        return payload["id"]

    async def process_batch(
        self,
        *,
        requests: t.Sequence[PendingRequestLike],
        client_factory: t.Callable[[], httpx.AsyncClient],
        queue_key: tuple[str, str | None],
    ) -> BatchSubmission:
        """
        Upload a JSONL file and create an OpenAI batch job.

        Parameters
        ----------
        requests : list[PendingRequestLike]
            Requests to submit in a single batch.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.
        queue_key : tuple[str, str | None]
            Queue key associated with the current batch.

        Returns
        -------
        BatchSubmission
            Metadata required by the batch poller.
        """
        if not requests:
            raise ValueError("Cannot process an empty request batch")

        base_url = self._normalize_base_url(url=requests[0].params["url"])
        endpoint = requests[0].params["endpoint"]
        log.debug(
            event="Resolved batch submission target",
            provider=self.name,
            base_url=base_url,
            endpoint=endpoint,
            request_count=len(requests),
        )
        api_headers = self.build_api_headers(
            headers=requests[0].params.get("headers") or dict(),
        )
        api_headers = self.build_internal_headers(headers=api_headers)

        jsonl_lines = self.build_jsonl_lines(requests=requests)
        log.debug(
            event="Built JSONL lines",
            provider=self.name,
            request_count=len(jsonl_lines),
        )

        file_id = await self._upload_batch_file(
            base_url=base_url,
            api_headers=api_headers,
            jsonl_lines=jsonl_lines,
            client_factory=client_factory,
        )
        log.info(
            event="Uploaded batch file",
            provider=self.name,
            file_id=file_id,
            request_count=len(jsonl_lines),
        )
        batch_id = await self._create_batch_job(
            base_url=base_url,
            api_headers=api_headers,
            file_id=file_id,
            endpoint=endpoint,
            queue_key=queue_key,
            client_factory=client_factory,
        )
        return BatchSubmission(
            base_url=base_url,
            api_headers=api_headers,
            batch_id=batch_id,
        )

    def from_batch_result(self, result_item: dict[str, t.Any]) -> httpx.Response:
        """
        Convert OpenAI batch results into an ``httpx.Response``.

        Parameters
        ----------
        result_item : dict[str, typing.Any]
            OpenAI batch result JSON line.

        Returns
        -------
        httpx.Response
            HTTP response derived from the batch result.
        """
        response = result_item.get("response")
        error = result_item.get("error")
        if response:
            status_code = int(response.get("status_code", 200))
            headers = dict(response.get("headers") or {})
            body = response.get("body")
        else:
            status_code = int(error.get("status_code", 500)) if error else 500
            headers = {}
            body = error or {"error": "Missing response"}

        content, content_headers = self.encode_body(body=body)
        headers.update(content_headers)

        return httpx.Response(
            status_code=status_code,
            headers=headers,
            content=content,
        )
