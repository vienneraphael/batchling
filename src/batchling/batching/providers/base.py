from __future__ import annotations

import json
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx


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
    path_prefixes: tuple[str, ...] = ()
    batchable_endpoints: tuple[tuple[str, str], ...] = ()

    def matches_url(self, url: str) -> bool:
        """
        Check whether a URL belongs to this provider.

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
        path = parsed.path or ""

        host_ok = True
        if self.hostnames:
            host_ok = hostname.endswith(self.hostnames) if hostname else bool(self.path_prefixes)

        path_ok = True
        if self.path_prefixes:
            path_ok = path.startswith(self.path_prefixes)

        return host_ok and path_ok

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

        return any(
            endpoint_method == normalized_method and endpoint_path == path
            for endpoint_method, endpoint_path in self.batchable_endpoints
        )

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
                return f"{normalized_path}?{parsed.query}"
            return normalized_path
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
            return f"{parsed.scheme}://{parsed.netloc}", self.normalize_url(url=url)

        if self.hostnames:
            return f"https://{self.hostnames[0]}", self.normalize_url(url=url)

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
            return params["json"]
        for key in ("body", "content", "data"):
            if params.get(key) is not None:
                return params[key]
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
            return None
        if isinstance(body, (dict, list)):
            return body
        if isinstance(body, (bytes, bytearray)):
            try:
                decoded = body.decode(encoding="utf-8")
            except Exception:
                return body.decode(encoding="utf-8", errors="replace")
            return self.maybe_parse_json(value=decoded)
        if isinstance(body, str):
            return self.maybe_parse_json(value=body)
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
            return json.loads(s=value)
        except Exception:
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
        return dict(headers) if headers else {}

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
        return {**headers, "x-batchling-internal": "1"}

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
            return b"", {}
        if isinstance(body, (dict, list)):
            return json.dumps(obj=body).encode(encoding="utf-8"), {
                "content-type": "application/json"
            }
        if isinstance(body, str):
            return body.encode(encoding="utf-8"), {"content-type": "text/plain"}
        if isinstance(body, (bytes, bytearray)):
            return bytes(body), {}
        return json.dumps(obj=body).encode(encoding="utf-8"), {"content-type": "application/json"}

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
