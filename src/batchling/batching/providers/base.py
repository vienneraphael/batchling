from __future__ import annotations

import json
import typing as t
from abc import ABC, abstractmethod
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

    def _summarize_value(self, *, value: t.Any) -> str:
        """
        Build a compact debug summary for arbitrary payload values.

        Parameters
        ----------
        value : typing.Any
            Value to summarize.

        Returns
        -------
        str
            Type/shape summary suitable for logs.
        """
        if value is None:
            return "none"
        if isinstance(value, dict):
            return f"dict(keys={list(value.keys())[:8]},len={len(value)})"
        if isinstance(value, list):
            return f"list(len={len(value)})"
        if isinstance(value, (bytes, bytearray)):
            return f"{type(value).__name__}(len={len(value)})"
        if isinstance(value, str):
            return f"str(len={len(value)})"
        return type(value).__name__

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

    def encode_body(self, *, body: t.Any) -> tuple[bytes, dict[str, str]]:
        """
        Encode response payloads into bytes and content headers.

        Parameters
        ----------
        body : typing.Any
            Response payload.

        Returns
        -------
        tuple[bytes, dict[str, str]]
            Encoded bytes and any content-type headers.
        """
        if body is None:
            log.debug(
                event="Encoded response body",
                provider=self.name,
                input_summary="none",
                output_bytes=0,
                content_type=None,
            )
            return b"", {}
        if isinstance(body, (dict, list)):
            encoded = json.dumps(obj=body).encode(encoding="utf-8")
            log.debug(
                event="Encoded response body",
                provider=self.name,
                input_summary=self._summarize_value(value=body),
                output_bytes=len(encoded),
                content_type="application/json",
            )
            return encoded, {"content-type": "application/json"}
        if isinstance(body, str):
            encoded = body.encode(encoding="utf-8")
            log.debug(
                event="Encoded response body",
                provider=self.name,
                input_summary=self._summarize_value(value=body),
                output_bytes=len(encoded),
                content_type="text/plain",
            )
            return encoded, {"content-type": "text/plain"}
        if isinstance(body, (bytes, bytearray)):
            encoded = bytes(body)
            log.debug(
                event="Encoded response body",
                provider=self.name,
                input_summary=self._summarize_value(value=body),
                output_bytes=len(encoded),
                content_type=None,
            )
            return encoded, {}
        encoded = json.dumps(obj=body).encode(encoding="utf-8")
        log.debug(
            event="Encoded response body",
            provider=self.name,
            input_summary=self._summarize_value(value=body),
            output_bytes=len(encoded),
            content_type="application/json",
        )
        return encoded, {"content-type": "application/json"}

    @abstractmethod
    def build_api_headers(self, *, headers: dict[str, str]) -> dict[str, str]:
        """
        Build provider API headers for batch submission/polling.

        Parameters
        ----------
        headers : dict[str, str]
            Original request headers.

        Returns
        -------
        dict[str, str]
            Provider API headers.
        """

    @abstractmethod
    async def process_batch(
        self,
        *,
        requests: t.Sequence[PendingRequestLike],
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> BatchSubmission:
        """
        Submit a provider batch and return polling metadata.

        Parameters
        ----------
        requests : list[PendingRequestLike]
            Requests to submit as a provider batch.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async HTTP client factory used for provider API calls.

        Returns
        -------
        BatchSubmission
            Metadata required by the core poller.
        """

    @abstractmethod
    def from_batch_result(self, result_item: dict[str, t.Any]) -> httpx.Response:
        """
        Convert a batch result JSON item into an ``httpx.Response``.

        Parameters
        ----------
        result_item : dict[str, typing.Any]
            Provider-specific JSONL result line.

        Returns
        -------
        httpx.Response
            Parsed HTTP response.
        """
