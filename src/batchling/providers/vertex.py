import json
import posixpath
import re
import typing as t
import uuid
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import quote

import httpx

from batchling.providers.base import (
    BaseProvider,
    BatchSubmission,
    BatchTerminalStatesLike,
    PendingRequestLike,
    PollSnapshot,
    ProviderRequestSpec,
    ResumeContext,
)


@dataclass(frozen=True)
class _GcsPrefix:
    bucket: str
    prefix: str


class VertexBatchTerminalStates(StrEnum):
    SUCCESS = "JOB_STATE_SUCCEEDED"
    FAILED = "JOB_STATE_FAILED"
    CANCELLED = "JOB_STATE_CANCELLED"
    EXPIRED = "JOB_STATE_EXPIRED"


class VertexProvider(BaseProvider):
    """Provider adapter for Vertex Gemini batch jobs."""

    name = "vertex"
    hostname = "aiplatform.googleapis.com"
    batchable_endpoints = (
        "/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent",
        "/v1beta1/projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent",
    )
    output_file_field_name: str = "output_file_id"
    error_file_field_name: str = "error_file_id"
    batch_terminal_states: type[BatchTerminalStatesLike] = VertexBatchTerminalStates
    custom_id_field_name: str = "key"
    supported_completion_windows = ("24h",)
    _regional_hostname_pattern = re.compile(pattern=r"^[a-z0-9-]+-aiplatform\.googleapis\.com$")
    _generate_content_endpoint_pattern = re.compile(
        pattern=(
            r"^/(?P<api_version>v1|v1beta1)/projects/(?P<project>[^/]+)/locations/(?P<location>[^/]+)/"
            r"publishers/google/models/(?P<model>[^/:]+):generateContent$"
        )
    )

    def matches_url(self, hostname: str) -> bool:
        """
        Check whether a URL belongs to Vertex by regional hostname.

        Parameters
        ----------
        hostname : str
            Candidate request hostname.

        Returns
        -------
        bool
            ``True`` when ``hostname`` is a regional Vertex hostname.
        """
        return bool(hostname) and (
            self._regional_hostname_pattern.fullmatch(string=hostname) is not None
        )

    def matches_batchable_endpoint(self, *, path: str) -> bool:
        """
        Check whether a request path is batchable for Vertex.

        Parameters
        ----------
        path : str
            Candidate request path.

        Returns
        -------
        bool
            ``True`` when ``path`` is a publisher Gemini ``generateContent`` path.
        """
        return self._generate_content_endpoint_pattern.fullmatch(string=path) is not None

    def extract_model_name(self, *, endpoint: str, body: bytes | None) -> str:
        """
        Extract Vertex Gemini model from the request path.

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
        """
        del body
        endpoint_match = self._generate_content_endpoint_pattern.fullmatch(string=endpoint)
        if endpoint_match is None:
            raise ValueError("Unsupported Vertex Gemini endpoint")
        model_name = endpoint_match.group("model")
        if not model_name.strip():
            raise ValueError("Vertex Gemini request path must include a model name")
        return model_name

    def build_jsonl_lines(
        self,
        *,
        requests: t.Sequence[PendingRequestLike],
    ) -> list[dict[str, t.Any]]:
        """
        Build Vertex JSONL input rows.

        Parameters
        ----------
        requests : list[PendingRequestLike]
            Pending requests to serialize.

        Returns
        -------
        list[dict[str, typing.Any]]
            JSONL-ready request rows.
        """
        return [
            {
                "key": request.custom_id,
                "request": json.loads(s=request.params["body"].decode(encoding="utf-8")),
            }
            for request in requests
        ]

    def build_poll_request_spec(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        batch_id: str,
    ) -> ProviderRequestSpec:
        """
        Build Vertex poll request metadata.
        """
        del base_url
        return ProviderRequestSpec(
            method="GET",
            path=self.build_batch_poll_path(batch_id=batch_id),
            headers=api_headers,
        )

    def build_batch_poll_path(self, *, batch_id: str) -> str:
        """
        Build Vertex poll path from a full batch resource name.

        Parameters
        ----------
        batch_id : str
            Vertex batch resource name without the leading API version.

        Returns
        -------
        str
            Relative poll path.
        """
        normalized_batch_id = batch_id.lstrip("/")
        if normalized_batch_id.startswith(("v1/", "v1beta1/")):
            return f"/{normalized_batch_id}"
        return f"/v1/{normalized_batch_id}"

    def extract_batch_status(self, *, payload: dict[str, t.Any]) -> str:
        """
        Extract Vertex batch status from the poll payload.

        Parameters
        ----------
        payload : dict[str, typing.Any]
            Vertex poll response payload.

        Returns
        -------
        str
            Vertex job state.
        """
        return str(object=payload.get("state") or "JOB_STATE_UNSPECIFIED")

    def get_progress_from_poll(
        self,
        *,
        payload: dict[str, t.Any],
        requests_count: int,
    ) -> tuple[int, float]:
        """
        Extract Vertex poll progress from ``completionStats``.

        Parameters
        ----------
        payload : dict[str, typing.Any]
            Vertex poll payload.
        requests_count : int
            Total request count for this batch.

        Returns
        -------
        tuple[int, float]
            Completed requests and completion percent.
        """
        completion_stats = payload.get("completionStats") or {}
        completed = max(
            0,
            self._coerce_int(value=completion_stats.get("successfulCount", 0))
            + self._coerce_int(value=completion_stats.get("failedCount", 0)),
        )
        if requests_count > 0:
            percent = (completed / requests_count) * 100.0
        else:
            percent = 0.0
        return completed, percent

    async def get_result_locator_from_poll_response(
        self,
        *,
        payload: dict[str, t.Any],
    ) -> str:
        """
        Get the Vertex GCS output directory from the poll response.

        Parameters
        ----------
        payload : dict[str, typing.Any]
            Vertex poll response payload.

        Returns
        -------
        str
            GCS output directory URI.
        """
        output_info = payload.get("outputInfo") or {}
        return str(object=output_info.get("gcsOutputDirectory") or "")

    async def get_output_file_id_from_poll_response(
        self,
        *,
        payload: dict[str, t.Any],
    ) -> str:
        """
        Vertex batches do not expose provider-hosted output file IDs.

        Parameters
        ----------
        payload : dict[str, typing.Any]
            Vertex poll response payload.

        Returns
        -------
        str
            Always empty for Vertex.
        """
        del payload
        return ""

    async def get_error_file_id_from_poll_response(
        self,
        *,
        payload: dict[str, t.Any],
    ) -> str:
        """
        Vertex batches do not expose provider-hosted error file IDs.

        Parameters
        ----------
        payload : dict[str, typing.Any]
            Vertex poll response payload.

        Returns
        -------
        str
            Always empty for Vertex.
        """
        del payload
        return ""

    async def parse_poll_response(
        self,
        *,
        payload: dict[str, t.Any],
        requests_count: int,
    ) -> PollSnapshot:
        """
        Parse Vertex poll payload into normalized snapshot.
        """
        return await super().parse_poll_response(
            payload=payload,
            requests_count=requests_count,
        )

    def build_resume_context(
        self,
        *,
        host: str,
        headers: dict[str, str] | None,
    ) -> ResumeContext:
        """
        Build Vertex resumed-polling context.
        """
        return super().build_resume_context(host=host, headers=headers)

    async def process_batch(
        self,
        *,
        requests: t.Sequence[PendingRequestLike],
        client_factory: t.Callable[[], httpx.AsyncClient],
        queue_key: tuple[str, str, str],
        completion_window: str,
        vertex_gcs_prefix: str | None = None,
    ) -> BatchSubmission:
        """
        Upload Vertex JSONL input to GCS and create a batch prediction job.

        Parameters
        ----------
        requests : list[PendingRequestLike]
            Requests to submit in a single batch.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.
        queue_key : tuple[str, str, str]
            Queue key associated with the current batch.
        completion_window : str
            Requested provider batch completion window.
        vertex_gcs_prefix : str | None
            GCS staging prefix for Vertex input/output artifacts.

        Returns
        -------
        BatchSubmission
            Metadata required by the batch poller.
        """
        del completion_window
        if not requests:
            raise ValueError("Cannot process an empty request batch")

        if not vertex_gcs_prefix:
            raise ValueError("Vertex provider requires batchify(vertex_gcs_prefix=...)")

        _, endpoint, model_name = queue_key
        endpoint_match = self._generate_content_endpoint_pattern.fullmatch(string=endpoint)
        if endpoint_match is None:
            raise ValueError("Unsupported Vertex Gemini endpoint")

        gcs_prefix = self._parse_gcs_prefix(uri=vertex_gcs_prefix)
        base_url = self._normalize_base_url(url=requests[0].params["url"])
        api_headers = self.build_internal_headers(
            headers=self.build_api_headers(headers=requests[0].params.get("headers") or {}),
        )

        batch_token = requests[0].custom_id.split(sep="-")[0]
        input_object_name = self._build_gcs_object_name(
            prefix=gcs_prefix.prefix,
            folder="inputs",
            model_name=model_name,
            suffix=f"{batch_token}-{uuid.uuid4().hex}.jsonl",
        )
        output_prefix = self._build_gcs_object_name(
            prefix=gcs_prefix.prefix,
            folder="outputs",
            model_name=model_name,
            suffix=f"{batch_token}-{uuid.uuid4().hex}",
        )
        input_uri = await self._upload_input_jsonl(
            gcs_prefix=gcs_prefix,
            object_name=input_object_name,
            jsonl_lines=self.build_jsonl_lines(requests=requests),
            api_headers=api_headers,
            client_factory=client_factory,
        )
        batch_id = await self._create_batch_job(
            base_url=base_url,
            api_headers=api_headers,
            endpoint_match=endpoint_match,
            input_uri=input_uri,
            output_uri_prefix=f"gs://{gcs_prefix.bucket}/{output_prefix}",
            model_name=model_name,
            request_id=batch_token,
            client_factory=client_factory,
        )
        return BatchSubmission(
            base_url=base_url,
            api_headers=api_headers,
            batch_id=batch_id,
        )

    async def fetch_results(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        batch_id: str,
        result_locator: str,
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> dict[str, httpx.Response]:
        """
        Fetch and decode Vertex JSONL results from GCS.

        Parameters
        ----------
        base_url : str
            Provider base URL.
        api_headers : dict[str, str]
            Provider API headers.
        batch_id : str
            Provider batch identifier.
        result_locator : str
            Vertex GCS output directory URI.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.

        Returns
        -------
        dict[str, httpx.Response]
            Provider responses keyed by custom ID.
        """
        del base_url
        if not result_locator:
            raise ValueError("Vertex batch completed without a GCS output directory")
        gcs_prefix = self._parse_gcs_prefix(uri=result_locator)
        object_names = await self._list_gcs_objects(
            bucket=gcs_prefix.bucket,
            prefix=gcs_prefix.prefix,
            api_headers=api_headers,
            client_factory=client_factory,
        )
        result_object_names = sorted(
            object_name
            for object_name in object_names
            if self._is_result_jsonl_object_name(object_name=object_name)
        )
        if not result_object_names:
            raise ValueError("Vertex batch completed without JSONL result artifacts")

        contents: list[str] = []
        for object_name in result_object_names:
            contents.append(
                await self._download_gcs_object(
                    bucket=gcs_prefix.bucket,
                    object_name=object_name,
                    api_headers=api_headers,
                    client_factory=client_factory,
                )
            )
        return self.decode_results_content(
            batch_id=batch_id,
            content="\n".join(content for content in contents if content.strip()),
        )

    def from_batch_result(self, result_item: dict[str, t.Any]) -> httpx.Response:
        """
        Convert Vertex batch results into an ``httpx.Response``.

        Parameters
        ----------
        result_item : dict[str, typing.Any]
            Vertex batch result JSON line.

        Returns
        -------
        httpx.Response
            HTTP response derived from the batch result.
        """
        response = result_item.get("response")
        status_payload = result_item.get("status") or {}
        if response is not None and not status_payload:
            status_code = 200
            headers: dict[str, str] = {}
            body = response
        else:
            status_code = 500
            headers = {}
            body = status_payload or {"error": "Missing response"}

        content, content_headers = self.encode_body(body=t.cast(dict[str, t.Any], body))
        headers.update(content_headers)
        return httpx.Response(
            status_code=status_code,
            headers=headers,
            content=content,
        )

    @staticmethod
    def _parse_gcs_prefix(*, uri: str) -> _GcsPrefix:
        """
        Parse and validate a GCS prefix URI.

        Parameters
        ----------
        uri : str
            GCS URI to parse.

        Returns
        -------
        _GcsPrefix
            Parsed bucket and object prefix.
        """
        if not uri.startswith("gs://"):
            raise ValueError("Vertex GCS prefix must start with 'gs://'")
        bucket_and_prefix = uri[5:]
        bucket, _, prefix = bucket_and_prefix.partition("/")
        normalized_prefix = prefix.strip("/")
        if not bucket.strip():
            raise ValueError("Vertex GCS prefix must include a bucket name")
        return _GcsPrefix(
            bucket=bucket.strip(),
            prefix=normalized_prefix,
        )

    @staticmethod
    def _is_result_jsonl_object_name(*, object_name: str) -> bool:
        """
        Check whether a GCS object is a Vertex JSONL result artifact.

        Parameters
        ----------
        object_name : str
            Candidate GCS object name.

        Returns
        -------
        bool
            ``True`` when the object stores Vertex predictions or errors.
        """
        if not object_name.endswith(".jsonl"):
            return False

        basename = posixpath.basename(object_name)
        return basename in {"predictions.jsonl", "errors.jsonl"} or basename.startswith(
            ("predictions_", "errors_")
        )

    @staticmethod
    def _build_gcs_object_name(*, prefix: str, folder: str, model_name: str, suffix: str) -> str:
        """
        Build a normalized GCS object path.

        Parameters
        ----------
        prefix : str
            GCS prefix without bucket.
        folder : str
            Object folder beneath the prefix.
        model_name : str
            Vertex model name.
        suffix : str
            Unique suffix for the object path.

        Returns
        -------
        str
            Normalized object path.
        """
        parts = [prefix, folder, model_name, suffix]
        return "/".join(part.strip("/") for part in parts if part.strip("/"))

    async def _upload_input_jsonl(
        self,
        *,
        gcs_prefix: _GcsPrefix,
        object_name: str,
        jsonl_lines: list[dict[str, t.Any]],
        api_headers: dict[str, str],
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> str:
        """
        Upload Vertex batch input JSONL to GCS.

        Parameters
        ----------
        gcs_prefix : _GcsPrefix
            Parsed GCS prefix.
        object_name : str
            GCS object name for the uploaded input.
        jsonl_lines : list[dict[str, typing.Any]]
            JSONL input rows.
        api_headers : dict[str, str]
            Provider API headers.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.

        Returns
        -------
        str
            Uploaded GCS URI.
        """
        payload = ("\n".join(json.dumps(obj=line) for line in jsonl_lines) + "\n").encode(
            encoding="utf-8"
        )
        upload_url = (
            "https://storage.googleapis.com/upload/storage/v1/b/"
            f"{quote(string=gcs_prefix.bucket, safe='')}/o"
            f"?uploadType=media&name={quote(string=object_name, safe='')}"
        )
        async with client_factory() as client:
            response = await client.post(
                url=upload_url,
                headers={**api_headers, "Content-Type": "application/jsonl"},
                content=payload,
            )
            response.raise_for_status()
        return f"gs://{gcs_prefix.bucket}/{object_name}"

    async def _create_batch_job(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        endpoint_match: re.Match[str],
        input_uri: str,
        output_uri_prefix: str,
        model_name: str,
        request_id: str,
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> str:
        """
        Create a Vertex batch prediction job.

        Parameters
        ----------
        base_url : str
            Vertex regional API base URL.
        api_headers : dict[str, str]
            Provider API headers.
        endpoint_match : re.Match[str]
            Matched publisher-model request endpoint.
        input_uri : str
            Uploaded GCS input URI.
        output_uri_prefix : str
            Destination GCS prefix for Vertex outputs.
        model_name : str
            Vertex publisher model name.
        request_id : str
            Stable per-batch identifier used in display names.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.

        Returns
        -------
        str
            Full Vertex batch resource name.
        """
        project = endpoint_match.group("project")
        location = endpoint_match.group("location")
        api_version = endpoint_match.group("api_version")
        path = f"/{api_version}/projects/{project}/locations/{location}/batchPredictionJobs"
        payload = {
            "displayName": f"batchling-{model_name}-{request_id}",
            "model": f"publishers/google/models/{model_name}",
            "inputConfig": {
                "instancesFormat": "jsonl",
                "gcsSource": {"uris": [input_uri]},
            },
            "outputConfig": {
                "predictionsFormat": "jsonl",
                "gcsDestination": {"outputUriPrefix": output_uri_prefix},
            },
            "instanceConfig": {
                "instanceType": "object",
                "keyField": "key",
            },
        }
        async with client_factory() as client:
            response = await client.post(
                url=f"{base_url}{path}",
                headers=api_headers,
                json=payload,
            )
            response.raise_for_status()
            response_json = response.json()
        name = response_json.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("Vertex batch creation response missing job name")
        return f"{api_version}/{name}"

    async def _list_gcs_objects(
        self,
        *,
        bucket: str,
        prefix: str,
        api_headers: dict[str, str],
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> list[str]:
        """
        List GCS objects under a prefix.

        Parameters
        ----------
        bucket : str
            GCS bucket name.
        prefix : str
            GCS object prefix.
        api_headers : dict[str, str]
            Provider API headers.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.

        Returns
        -------
        list[str]
            Object names under the prefix.
        """
        list_url = f"https://storage.googleapis.com/storage/v1/b/{quote(string=bucket, safe='')}/o"
        object_names: list[str] = []
        page_token: str | None = None
        async with client_factory() as client:
            while True:
                params: dict[str, str] = {"prefix": prefix}
                if page_token:
                    params["pageToken"] = page_token
                response = await client.get(
                    url=list_url,
                    headers=api_headers,
                    params=params,
                )
                response.raise_for_status()
                payload = response.json()
                object_names.extend(
                    str(object=item["name"])
                    for item in payload.get("items") or []
                    if "name" in item
                )
                next_page_token = payload.get("nextPageToken")
                if not isinstance(next_page_token, str) or not next_page_token:
                    break
                page_token = next_page_token
        return object_names

    async def _download_gcs_object(
        self,
        *,
        bucket: str,
        object_name: str,
        api_headers: dict[str, str],
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> str:
        """
        Download one GCS object as text.

        Parameters
        ----------
        bucket : str
            GCS bucket name.
        object_name : str
            GCS object name.
        api_headers : dict[str, str]
            Provider API headers.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.

        Returns
        -------
        str
            Object content decoded as text.
        """
        download_url = (
            "https://storage.googleapis.com/storage/v1/b/"
            f"{quote(string=bucket, safe='')}/o/{quote(string=object_name, safe='')}"
            "?alt=media"
        )
        async with client_factory() as client:
            response = await client.get(
                url=download_url,
                headers=api_headers,
            )
            response.raise_for_status()
        return response.text
