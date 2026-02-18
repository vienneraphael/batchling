import json
import re
import typing as t
from enum import StrEnum

import httpx
import structlog

from batchling.providers.base import (
    BaseProvider,
    BatchTerminalStatesLike,
    PendingRequestLike,
)

log = structlog.get_logger(__name__)


class GeminiBatchTerminalStates(StrEnum):
    SUCCESS = "BATCH_STATE_SUCCEEDED"
    FAILED = "BATCH_STATE_FAILED"
    CANCELLED = "BATCH_STATE_CANCELLED"
    EXPIRED = "BATCH_STATE_EXPIRED"


class GeminiProvider(BaseProvider):
    """Provider adapter for Gemini's HTTP and Batch APIs."""

    name = "gemini"
    hostnames = ("generativelanguage.googleapis.com",)
    batchable_endpoints = ("/v1beta/models/{model}:generateContent",)
    file_upload_endpoint = "/upload/v1beta/files"
    batch_endpoint = "/v1beta/models/{model}:batchGenerateContent"
    batch_terminal_states: type[BatchTerminalStatesLike] = GeminiBatchTerminalStates
    _generate_content_endpoint_pattern = re.compile(
        pattern=r"^/v1beta/models/(?P<model>[^/]+):generateContent$"
    )
    error_file_field_name: str = "error"
    custom_id_field_name: str = "key"

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
        jsonl_lines = []
        for request in requests:
            body = json.loads(s=request.params["body"].decode(encoding="utf-8"))
            jsonl_lines.append(
                {
                    "key": request.custom_id,
                    "request": body,
                }
            )
        return jsonl_lines

    def extract_model_name(self, *, endpoint: str, body: bytes | None) -> str:
        """
        Extract Gemini model from endpoint path for queue partitioning.

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
        endpoint_match = self._generate_content_endpoint_pattern.fullmatch(string=endpoint)
        if endpoint_match is not None:
            model_name = endpoint_match.group("model")
            if model_name.strip():
                return model_name

        return super().extract_model_name(endpoint=endpoint, body=body)

    def build_batch_submit_path(self, *, queue_key: tuple[str, str, str]) -> str:
        """
        Build Gemini batch submit path.

        Parameters
        ----------
        queue_key : tuple[str, str, str]
            Queue key associated with the current batch.

        Returns
        -------
        str
            Submit path with model segment.
        """
        _, _, model_name = queue_key
        return f"/v1beta/models/{model_name}:batchGenerateContent"

    def build_batch_poll_path(self, *, batch_id: str) -> str:
        """
        Build Gemini batch poll path.

        Parameters
        ----------
        batch_id : str
            Provider batch identifier.

        Returns
        -------
        str
            Poll path for Gemini batch status.
        """
        return f"/v1beta/batches/{batch_id}"

    def build_batch_results_path(self, *, file_id: str | None, batch_id: str) -> str:
        """
        Build Gemini batch results path.

        Parameters
        ----------
        file_id : str | None
            Unused by Gemini result retrieval.
        batch_id : str
            Provider batch identifier.

        Returns
        -------
        str
            Results path for Gemini batch output.
        """
        return f"/download/v1beta/files/{file_id}:download?alt=media"

    def extract_batch_status(self, *, payload: dict[str, t.Any]) -> str:
        """
        Extract Gemini batch status from nested poll payload fields.

        Parameters
        ----------
        payload : dict[str, typing.Any]
            Gemini poll response payload.

        Returns
        -------
        str
            Batch status value.
        """
        metadata_payload = payload.get("metadata") or {}
        return metadata_payload.get("state") or "created"

    async def get_output_file_id_from_poll_response(
        self,
        *,
        payload: dict[str, t.Any],
    ) -> str:
        """
        Get the output file ID from the poll response.
        """

        response = payload.get("response") or {}
        return response.get("responsesFile") or ""

    def _get_batch_id_from_response(self, *, response_json: dict) -> str:
        """
        Get the batch ID from the response.
        """
        return response_json["name"].split("/")[-1]

    async def _create_resumable_upload_session(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> str:
        """
        Create a resumable upload session for the provider.

        Parameters
        ----------
        base_url : str
            base URL.
        api_headers : dict[str, str]
            API headers.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.

        Returns
        -------
        str
            Upload URL.
        """
        additional_headers = {
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Type": "application/json",
            "Content-Type": "application/json",
        }
        data = {
            "file": {
                "display_name": "batch.jsonl",
            }
        }
        async with client_factory() as client:
            response = await client.post(
                url=f"{base_url}{self.file_upload_endpoint}",
                headers={**api_headers, **additional_headers},
                json=data,
            )
            response.raise_for_status()
            upload_url = response.headers.get("X-Goog-Upload-URL")
        return upload_url

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
        log.debug(
            event="Creating resumable upload session",
            url=f"{base_url}{self.file_upload_endpoint}",
            headers={k: "***" for k in api_headers.keys()},
        )
        upload_url = await self._create_resumable_upload_session(
            base_url=base_url,
            api_headers=api_headers,
            client_factory=client_factory,
        )
        additional_headers = {
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        }

        file_content = ("\n".join(json.dumps(obj=line) for line in jsonl_lines) + "\n").encode(
            encoding="utf-8"
        )
        log.debug(
            event="Uploading batch file",
            url=upload_url,
        )
        async with client_factory() as client:
            response = await client.post(
                url=upload_url,
                headers={**api_headers, **additional_headers},
                content=file_content,
            )
            response.raise_for_status()
            json_response = response.json()
        file_payload = json_response.get("file") or {}
        file_name = file_payload.get("name")
        if not isinstance(file_name, str) or not file_name:
            raise ValueError("Gemini upload response missing file.name")
        return file_name

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
            "batch": {
                "display_name": "batchling",
                "input_config": {
                    "file_name": file_id,
                },
            }
        }
