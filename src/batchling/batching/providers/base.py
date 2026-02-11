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

    def matches_url(self, url: str) -> bool:
        """
        Check whether a URL belongs to this provider by hostname.

        Parameters
        ----------
        url : str
            Candidate request URL.

        Returns
        -------
        bool
            ``True`` if the URL matches this provider.
        """
        parsed = urlparse(url=url)
        hostname = (parsed.hostname or "").lower()
        is_match = bool(hostname) and hostname.endswith(self.hostnames)
        log.debug(
            event="Provider URL match evaluated",
            provider=self.name,
            input_url=url,
            parsed_hostname=hostname,
            matched=is_match,
        )
        return is_match

    def is_batchable_request(self, *, method: str, url: str) -> bool:
        """
        Check whether an HTTP request should be routed into batching.

        Parameters
        ----------
        method : str
            HTTP method for the request.
        url : str
            Candidate request URL.

        Returns
        -------
        bool
            ``True`` if this request is explicitly batchable for the provider.
        """
        if not self.matches_url(url=url):
            return False

        parsed = urlparse(url=url)
        path = parsed.path or "/"
        normalized_method = method.upper()

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

    def normalize_url(self, url: str) -> str:
        """
        Normalize request URLs into provider batch endpoint format.

        Parameters
        ----------
        url : str
            Original request URL.

        Returns
        -------
        str
            Path-only URL (including query string) for absolute URLs, or the
            original value for relative inputs.
        """
        parsed = urlparse(url=url)
        if parsed.scheme and parsed.netloc:
            normalized_path = parsed.path or "/"
            if parsed.query:
                normalized_url = f"{normalized_path}?{parsed.query}"
                log.debug(
                    event="Normalized absolute URL",
                    provider=self.name,
                    input_url=url,
                    output_url=normalized_url,
                )
                return normalized_url
            log.debug(
                event="Normalized absolute URL",
                provider=self.name,
                input_url=url,
                output_url=normalized_path,
            )
            return normalized_path
        log.debug(
            event="Kept relative URL",
            provider=self.name,
            input_url=url,
            output_url=url,
        )
        return url

    def extract_base_and_endpoint(self, *, url: str) -> tuple[str, str]:
        """
        Extract provider base URL and normalized endpoint.

        Parameters
        ----------
        url : str
            Original request URL.

        Returns
        -------
        tuple[str, str]
            Provider base URL and normalized endpoint path.
        """
        parsed = urlparse(url=url)
        if parsed.scheme and parsed.netloc:
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            endpoint = self.normalize_url(url=url)
            log.debug(
                event="Extracted provider base/endpoint",
                provider=self.name,
                input_url=url,
                base_url=base_url,
                endpoint=endpoint,
            )
            return base_url, endpoint

        if self.hostnames:
            base_url = f"https://{self.hostnames[0]}"
            endpoint = self.normalize_url(url=url)
            log.debug(
                event="Extracted fallback base/endpoint",
                provider=self.name,
                input_url=url,
                base_url=base_url,
                endpoint=endpoint,
            )
            return base_url, endpoint

        raise ValueError(f"Unable to determine base URL for request: {url}")

    def extract_body(self, *, params: dict[str, t.Any]) -> t.Any:
        """
        Extract request body from captured hook params.

        Parameters
        ----------
        params : dict[str, typing.Any]
            Hook parameters captured from HTTP clients.

        Returns
        -------
        typing.Any
            Request body value, if any.
        """
        if params.get("json") is not None:
            extracted = params["json"]
            log.debug(
                event="Extracted request body",
                provider=self.name,
                source_key="json",
                output_summary=self._summarize_value(value=extracted),
            )
            return extracted
        for key in ("body", "content", "data"):
            if params.get(key) is not None:
                extracted = params[key]
                log.debug(
                    event="Extracted request body",
                    provider=self.name,
                    source_key=key,
                    output_summary=self._summarize_value(value=extracted),
                )
                return extracted
        log.debug(
            event="Extracted request body",
            provider=self.name,
            source_key=None,
            output_summary="none",
        )
        return None

    def normalize_body(self, *, body: t.Any) -> t.Any:
        """
        Normalize request bodies for JSONL serialization.

        Parameters
        ----------
        body : typing.Any
            Original request body.

        Returns
        -------
        typing.Any
            Normalized body.
        """
        if body is None:
            log.debug(
                event="Normalized request body",
                provider=self.name,
                input_summary="none",
                output_summary="none",
            )
            return None
        if isinstance(body, (dict, list)):
            log.debug(
                event="Normalized request body",
                provider=self.name,
                input_summary=self._summarize_value(value=body),
                output_summary=self._summarize_value(value=body),
            )
            return body
        if isinstance(body, (bytes, bytearray)):
            try:
                decoded = body.decode(encoding="utf-8")
            except Exception:
                normalized = body.decode(encoding="utf-8", errors="replace")
                log.debug(
                    event="Normalized request body",
                    provider=self.name,
                    input_summary=self._summarize_value(value=body),
                    output_summary=self._summarize_value(value=normalized),
                )
                return normalized
            normalized = self.maybe_parse_json(value=decoded)
            log.debug(
                event="Normalized request body",
                provider=self.name,
                input_summary=self._summarize_value(value=body),
                output_summary=self._summarize_value(value=normalized),
            )
            return normalized
        if isinstance(body, str):
            normalized = self.maybe_parse_json(value=body)
            log.debug(
                event="Normalized request body",
                provider=self.name,
                input_summary=self._summarize_value(value=body),
                output_summary=self._summarize_value(value=normalized),
            )
            return normalized
        log.debug(
            event="Normalized request body",
            provider=self.name,
            input_summary=self._summarize_value(value=body),
            output_summary=self._summarize_value(value=body),
        )
        return body

    def maybe_parse_json(self, *, value: str) -> t.Any:
        """
        Parse JSON strings when possible.

        Parameters
        ----------
        value : str
            Candidate JSON string.

        Returns
        -------
        typing.Any
            Parsed JSON data, or the original string if parsing fails.
        """
        try:
            parsed = json.loads(s=value)
            log.debug(
                event="Parsed JSON body value",
                provider=self.name,
                input_summary=self._summarize_value(value=value),
                output_summary=self._summarize_value(value=parsed),
            )
            return parsed
        except Exception:
            log.debug(
                event="Preserved non-JSON body value",
                provider=self.name,
                input_summary=self._summarize_value(value=value),
            )
            return value

    def normalize_headers(
        self,
        *,
        headers: dict[str, str] | None,
    ) -> dict[str, str]:
        """
        Normalize request headers to a mutable dictionary.

        Parameters
        ----------
        headers : dict[str, str] | None
            Raw request headers.

        Returns
        -------
        dict[str, str]
            Mutable header mapping.
        """
        normalized_headers = dict(headers) if headers else {}
        log.debug(
            event="Normalized request headers",
            provider=self.name,
            input_header_count=len(headers) if headers else 0,
            output_header_count=len(normalized_headers),
            output_header_keys=list(normalized_headers.keys()),
        )
        return normalized_headers

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
        jsonl_lines: list[dict[str, t.Any]] = []
        for request in requests:
            body = self.normalize_body(
                body=self.extract_body(params=request.params),
            )
            line: dict[str, t.Any] = {
                "custom_id": request.custom_id,
                "method": request.params["method"],
                "url": self.normalize_url(url=request.params["url"]),
            }
            if body is not None:
                line["body"] = body
            jsonl_lines.append(line)
            log.debug(
                event="Built provider JSONL line",
                provider=self.name,
                custom_id=request.custom_id,
                method=request.params["method"],
                input_url=request.params["url"],
                output_url=line["url"],
                body_summary=self._summarize_value(value=body),
            )
        log.debug(
            event="Built provider JSONL payload",
            provider=self.name,
            request_count=len(requests),
            line_count=len(jsonl_lines),
        )
        return jsonl_lines

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
