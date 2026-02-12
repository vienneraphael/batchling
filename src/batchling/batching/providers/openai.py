from __future__ import annotations

import json
import typing as t

import httpx
import structlog

from batchling.batching.providers.base import (
    BaseProvider,
    BatchSubmission,
    PendingRequestLike,
)
from batchling.utils.api import get_default_api_key_from_provider

log = structlog.get_logger(__name__)


class OpenAIProvider(BaseProvider):
    """Provider adapter for OpenAI's HTTP and Batch APIs."""

    name = "openai"
    hostnames = ("api.openai.com",)
    batchable_endpoints = (
        "/v1/responses",
        "/v1/chat/completions",
        "/v1/embeddings",
        "/v1/completions",
        "/v1/moderations",
        "/v1/images/generations",
        "/v1/images/edits",
    )
    terminal_states = {"completed", "failed", "cancelled", "expired"}

    def build_api_headers(self, *, headers: dict[str, str]) -> dict[str, str]:
        """
        Build OpenAI API headers for batch endpoints.

        Parameters
        ----------
        headers : dict[str, str]
            Original request headers.

        Returns
        -------
        dict[str, str]
            OpenAI API headers.
        """
        api_headers: dict[str, str] = {}
        for key, value in headers.items():
            lower_key = key.lower()
            if lower_key == "authorization":
                api_headers["Authorization"] = value
            elif lower_key.startswith("openai-"):
                api_headers[key] = value

        if "Authorization" not in api_headers:
            api_key = get_default_api_key_from_provider(provider=self.name)
            api_headers["Authorization"] = f"Bearer {api_key}"
        log.debug(
            event="Built provider API headers",
            provider=self.name,
            input_header_keys=list(headers.keys()),
            output_header_keys=list(api_headers.keys()),
            has_authorization="Authorization" in api_headers,
        )
        return api_headers

    async def process_batch(
        self,
        *,
        requests: t.Sequence[PendingRequestLike],
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> BatchSubmission:
        """
        Upload a JSONL file and create an OpenAI batch job.

        Parameters
        ----------
        requests : list[PendingRequestLike]
            Requests to submit in a single batch.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.

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
            client_factory=client_factory,
        )
        return BatchSubmission(
            base_url=base_url,
            api_headers=api_headers,
            batch_id=batch_id,
        )

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
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.

        Returns
        -------
        str
            OpenAI batch ID.
        """
        async with client_factory() as client:
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
        return payload["id"]

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
