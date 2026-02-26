from __future__ import annotations

import inspect
import json
import re
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


@dataclass(frozen=True)
class ProviderRequestSpec:
    """
    Provider-defined HTTP request shape executed by the batcher transport.

    Parameters
    ----------
    method : str
        HTTP method.
    path : str
        Relative provider path.
    headers : dict[str, str]
        Request headers.
    json_body : dict[str, typing.Any] | None
        Optional JSON payload.
    content : bytes | None
        Optional raw request body.
    files : dict[str, typing.Any] | None
        Optional multipart files payload.
    data : dict[str, typing.Any] | None
        Optional form data payload.
    """

    method: str
    path: str
    headers: dict[str, str]
    json_body: dict[str, t.Any] | None = None
    content: bytes | None = None
    files: dict[str, t.Any] | None = None
    data: dict[str, t.Any] | None = None


@dataclass(frozen=True)
class PollSnapshot:
    """
    Normalized provider poll snapshot.

    Parameters
    ----------
    status : str
        Provider status value.
    output_file_id : str
        Output file identifier when available.
    error_file_id : str
        Error file identifier when available.
    """

    status: str
    output_file_id: str
    error_file_id: str


@dataclass(frozen=True)
class ResumeContext:
    """
    Resumed-polling context derived from an intercepted cache-hit request.

    Parameters
    ----------
    base_url : str
        Provider base URL used for resumed polling.
    api_headers : dict[str, str]
        Provider API headers used for resumed polling.
    """

    base_url: str
    api_headers: dict[str, str]


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
    hostname: str = ""
    batch_method: str = "POST"
    batchable_endpoints: tuple[str, ...] = ()
    is_file_based: bool = True
    file_upload_endpoint: str
    file_content_endpoint: str
    batch_endpoint: str
    batch_terminal_states: type[BatchTerminalStatesLike]
    batch_status_field_name: str = "status"
    custom_id_field_name: str = "custom_id"
    output_file_field_name: str
    error_file_field_name: str

    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        """
        Validate provider hostname configuration at class-definition time.

        Parameters
        ----------
        **kwargs : dict[str, typing.Any]
            Extra subclass construction kwargs.

        Raises
        ------
        TypeError
            If the provider uses removed ``hostnames`` or defines invalid ``hostname``.
        """
        super().__init_subclass__(**kwargs)
        if cls is BaseProvider:
            return

        if "hostnames" in cls.__dict__:
            raise TypeError(
                "Provider `hostnames` has been removed; define a single `hostname` string instead."
            )

        if inspect.isabstract(object=cls):
            return

        hostname = getattr(cls, "hostname", "")
        if not isinstance(hostname, str) or not hostname.strip():
            raise TypeError(
                f"{cls.__name__} must define non-empty class attribute `hostname: str`."
            )

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
        configured_hostname = self.hostname.lower()
        is_match = bool(hostname) and hostname == configured_hostname
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
        endpoint_ok = self.matches_batchable_endpoint(path=path)
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

    def matches_batchable_endpoint(self, *, path: str) -> bool:
        """
        Check whether a request path is batchable for this provider.

        Parameters
        ----------
        path : str
            Candidate request path.

        Returns
        -------
        bool
            ``True`` when ``path`` matches a configured batchable endpoint.
            Endpoints may include template placeholders such as ``{model}``,
            which match one path segment (excluding ``/``).
        """
        for endpoint in self.batchable_endpoints:
            if "{" not in endpoint:
                if path == endpoint:
                    return True
                continue

            escaped_endpoint = re.escape(pattern=endpoint)
            endpoint_pattern = re.sub(
                pattern=r"\\\{[^{}]+\\\}",
                repl=r"[^/]+",
                string=escaped_endpoint,
            )
            if re.fullmatch(pattern=endpoint_pattern, string=path) is not None:
                return True

        return False

    def extract_model_name(self, *, endpoint: str, body: bytes | None) -> str:
        """
        Extract request model name used for queue partitioning.

        Parameters
        ----------
        endpoint : str
            Request endpoint path.
        body : bytes | None
            Raw request body captured by hooks.

        Returns
        -------
        str
            Non-empty model name.

        Raises
        ------
        ValueError
            If body is missing, invalid JSON, or model is absent.
        """
        del endpoint
        if body is None:
            raise ValueError("Batch request JSON body is required for strict homogeneous batching")

        body_text = body.decode(encoding="utf-8")
        payload = json.loads(s=body_text)
        model = payload.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Batch request JSON must include non-empty string 'model'")
        return model

    def build_batch_submit_path(self, *, queue_key: tuple[str, str, str]) -> str:
        """
        Build the provider path used to submit a batch.

        Parameters
        ----------
        queue_key : tuple[str, str, str]
            Queue key associated with the current batch.

        Returns
        -------
        str
            Relative submit path.
        """
        del queue_key
        return self.batch_endpoint

    def build_batch_poll_path(self, *, batch_id: str) -> str:
        """
        Build the provider path used to poll a batch.

        Parameters
        ----------
        batch_id : str
            Provider batch identifier.

        Returns
        -------
        str
            Relative poll path.
        """
        return f"{self.batch_endpoint}/{batch_id}"

    def build_poll_request_spec(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        batch_id: str,
    ) -> ProviderRequestSpec:
        """
        Build poll request metadata for the batcher transport.

        Parameters
        ----------
        base_url : str
            Provider base URL.
        api_headers : dict[str, str]
            Provider API headers.
        batch_id : str
            Provider batch ID.

        Returns
        -------
        ProviderRequestSpec
            Poll request specification.
        """
        del base_url
        return ProviderRequestSpec(
            method="GET",
            path=self.build_batch_poll_path(batch_id=batch_id),
            headers=api_headers,
        )

    def build_batch_results_path(self, *, file_id: str | None, batch_id: str) -> str:
        """
        Build the provider path used to download batch results.

        Parameters
        ----------
        file_id : str | None
            Provider output or error file identifier.
        batch_id : str
            Provider batch identifier.

        Returns
        -------
        str
            Relative results path.

        Raises
        ------
        ValueError
            If this provider requires a file id and it is missing.
        """
        del batch_id
        if not file_id:
            raise ValueError("Batch completed without output or error file")
        return self.file_content_endpoint.format(id=file_id)

    def build_results_request_spec(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        file_id: str | None,
        batch_id: str,
    ) -> ProviderRequestSpec:
        """
        Build results download request metadata for the batcher transport.

        Parameters
        ----------
        base_url : str
            Provider base URL.
        api_headers : dict[str, str]
            Provider API headers.
        file_id : str | None
            Provider output or error file identifier.
        batch_id : str
            Provider batch identifier.

        Returns
        -------
        ProviderRequestSpec
            Results request specification.
        """
        del base_url
        return ProviderRequestSpec(
            method="GET",
            path=self.build_batch_results_path(file_id=file_id, batch_id=batch_id),
            headers=api_headers,
        )

    def extract_batch_status(self, *, payload: dict[str, t.Any]) -> str:
        """
        Extract provider batch status from a poll payload.

        Parameters
        ----------
        payload : dict[str, typing.Any]
            Provider poll response payload.

        Returns
        -------
        str
            Normalized status string.
        """
        status = payload.get(self.batch_status_field_name, "created")
        return str(object=status)

    async def parse_poll_response(
        self,
        *,
        payload: dict[str, t.Any],
    ) -> PollSnapshot:
        """
        Normalize poll payload into a provider-independent snapshot.

        Parameters
        ----------
        payload : dict[str, typing.Any]
            Provider poll payload.

        Returns
        -------
        PollSnapshot
            Poll snapshot.
        """
        status = self.extract_batch_status(payload=payload)
        output_file_id = await self.get_output_file_id_from_poll_response(payload=payload)
        error_file_id = await self.get_error_file_id_from_poll_response(payload=payload)
        return PollSnapshot(
            status=status,
            output_file_id=str(object=output_file_id),
            error_file_id=str(object=error_file_id),
        )

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
            elif lower_key == "x-api-key":
                api_headers["X-Api-Key"] = value
            elif lower_key == "x-goog-api-key":
                api_headers["x-goog-api-key"] = value
            elif lower_key.startswith(f"{self.name}-"):
                api_headers[key] = value
        return api_headers

    def build_resume_context(
        self,
        *,
        host: str,
        headers: dict[str, str] | None,
    ) -> ResumeContext:
        """
        Build resumed-polling context for cache-hit routing.

        Parameters
        ----------
        host : str
            Intercepted request host.
        headers : dict[str, str] | None
            Intercepted request headers.

        Returns
        -------
        ResumeContext
            Resumed polling context.
        """
        api_headers = self.build_internal_headers(
            headers=self.build_api_headers(headers=headers or {}),
        )
        return ResumeContext(
            base_url=self._normalize_base_url(url=host),
            api_headers=api_headers,
        )

    def _build_batch_file_files_payload(
        self, *, file_content: bytes
    ) -> dict[str, tuple[str, bytes, str]]:
        """
        Build a batch file files payload for the provider.
        """
        return {
            "file": ("batch.jsonl", file_content, "application/jsonl"),
        }

    def _build_batch_file_data_payload(self) -> dict[str, str]:
        """
        Build a batch file data payload for the provider.
        """
        return {
            "purpose": "batch",
        }

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
        files = self._build_batch_file_files_payload(file_content=file_content)
        data = self._build_batch_file_data_payload()

        log.debug(
            event="Uploading batch file",
            url=f"{base_url}{self.file_upload_endpoint}",
            headers={k: "***" for k in api_headers.keys()},
            files=files,
            data=data,
        )

        async with client_factory() as client:
            response = await client.post(
                url=f"{base_url}{self.file_upload_endpoint}",
                headers=api_headers,
                files=files,
                data=data,
            )
            response.raise_for_status()
            json_response = response.json()
        return json_response["id"]

    async def build_file_based_batch_payload(
        self,
        *,
        file_id: str,
        endpoint: str,
        queue_key: tuple[str, str, str],
    ) -> dict[str, t.Any]:
        """
        Build a batch payload for the provider.
        """
        del queue_key
        return {
            "input_file_id": file_id,
            "endpoint": endpoint,
            "completion_window": "24h",
            "metadata": {"description": "batchling runtime batch"},
        }

    async def build_inline_batch_payload(
        self,
        *,
        jsonl_lines: list[dict[str, t.Any]],
    ) -> dict[str, t.Any]:
        """
        Build an inline batch payload for the provider.
        """
        return {
            "requests": jsonl_lines,
        }

    async def get_output_file_id_from_poll_response(
        self,
        *,
        payload: dict[str, t.Any],
    ) -> str:
        """
        Get the output file ID from the poll response.
        """
        return payload.get(self.output_file_field_name) or ""

    async def get_error_file_id_from_poll_response(
        self,
        *,
        payload: dict[str, t.Any],
    ) -> str:
        """
        Get the error file ID from the poll response.
        """
        return payload.get(self.error_file_field_name) or ""

    def _get_batch_id_from_response(self, *, response_json: dict) -> str:
        """
        Get the batch ID from the response.
        """
        return response_json["id"]

    async def _create_file_based_batch_job(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        file_id: str,
        endpoint: str,
        queue_key: tuple[str, str, str],
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> str:
        """
        Create an OpenAI batch job.

        Parameters
        ----------
        base_url : str
            base URL.
        api_headers : dict[str, str]
            API headers.
        file_id : str
            Uploaded input file ID.
        endpoint : str
            Endpoint path included in the batch job.
        queue_key : tuple[str, str, str]
            Queue key associated with the current batch.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.

        Returns
        -------
        str
            batch ID.
        """
        submit_path = self.build_batch_submit_path(queue_key=queue_key)
        payload = await self.build_file_based_batch_payload(
            file_id=file_id,
            endpoint=endpoint,
            queue_key=queue_key,
        )
        log.debug(
            "Sending batch request",
            url=f"{base_url}{submit_path}",
            headers={k: "***" for k in api_headers.keys()},
            payload=payload,
        )
        async with client_factory() as client:
            response = await client.post(
                url=f"{base_url}{submit_path}", headers=api_headers, json=payload
            )
            response.raise_for_status()
            json_response = response.json()
        return self._get_batch_id_from_response(response_json=json_response)

    async def _create_inline_batch_job(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        jsonl_lines: list[dict[str, t.Any]],
        queue_key: tuple[str, str, str],
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> str:
        """
        Create an inline batch job.

        Parameters
        ----------
        base_url : str
            base URL.
        api_headers : dict[str, str]
            API headers.
        jsonl_lines : list[dict[str, typing.Any]]
            JSONL line payloads.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.

        Returns
        -------
        str
            batch ID.
        """
        submit_path = self.build_batch_submit_path(queue_key=queue_key)
        payload = await self.build_inline_batch_payload(jsonl_lines=jsonl_lines)
        log.debug(
            event="Sending inline batch request",
            url=f"{base_url}{submit_path}",
            headers={k: "***" for k in api_headers.keys()},
            payload=payload,
        )
        async with client_factory() as client:
            response = await client.post(
                url=f"{base_url}{submit_path}", headers=api_headers, json=payload
            )
            response.raise_for_status()
            json_response = response.json()
        return self._get_batch_id_from_response(response_json=json_response)

    async def process_batch(
        self,
        *,
        requests: t.Sequence[PendingRequestLike],
        client_factory: t.Callable[[], httpx.AsyncClient],
        queue_key: tuple[str, str, str],
    ) -> BatchSubmission:
        """
        Upload a JSONL file and create an OpenAI batch job.

        Parameters
        ----------
        requests : list[PendingRequestLike]
            Requests to submit in a single batch.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.
        queue_key : tuple[str, str, str]
            Queue key associated with the current batch.

        Returns
        -------
        BatchSubmission
            Metadata required by the batch poller.
        """
        if not requests:
            raise ValueError("Cannot process an empty request batch")

        _, endpoint, _ = queue_key
        base_url = self._normalize_base_url(url=requests[0].params["url"])
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
        if self.is_file_based:
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
            batch_id = await self._create_file_based_batch_job(
                base_url=base_url,
                api_headers=api_headers,
                file_id=file_id,
                endpoint=endpoint,
                queue_key=queue_key,
                client_factory=client_factory,
            )
        else:
            batch_id = await self._create_inline_batch_job(
                base_url=base_url,
                api_headers=api_headers,
                jsonl_lines=jsonl_lines,
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
        Convert provider batch results into an ``httpx.Response``.

        Parameters
        ----------
        result_item : dict[str, typing.Any]
            provider batch result JSON line.

        Returns
        -------
        httpx.Response
            HTTP response derived from the batch result.
        """
        response = result_item.get("response")
        error = result_item.get("error") or {}
        if response:
            status_code = int(response.get("status_code", 200))
            headers = dict(response.get("headers") or {})
            body = response.get("body")
        else:
            status_code = int(error.get("status_code", 500))
            headers = {}
            body = error or {"error": "Missing response"}

        content, content_headers = self.encode_body(body=body)
        headers.update(content_headers)

        return httpx.Response(
            status_code=status_code,
            headers=headers,
            content=content,
        )

    def decode_results_content(
        self,
        *,
        batch_id: str,
        content: str,
    ) -> dict[str, httpx.Response]:
        """
        Decode provider JSONL batch content into responses keyed by custom ID.

        Parameters
        ----------
        batch_id : str
            Batch ID for observability.
        content : str
            Raw JSONL content.

        Returns
        -------
        dict[str, httpx.Response]
            Responses keyed by provider custom ID.
        """
        decoded: dict[str, httpx.Response] = {}
        for line in content.splitlines():
            if not line.strip():
                continue
            result_item = json.loads(s=line)
            custom_id = result_item.get(self.custom_id_field_name)
            if custom_id is None:
                log.debug(
                    event="Batch result missing custom_id",
                    provider=self.name,
                    batch_id=batch_id,
                )
                continue
            decoded[str(object=custom_id)] = self.from_batch_result(result_item=result_item)
        return decoded
