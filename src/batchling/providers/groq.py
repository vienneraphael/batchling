import typing as t

import httpx

from batchling.providers.base import (
    PendingRequestLike,
    PollSnapshot,
    ProviderRequestSpec,
    ResumeContext,
)
from batchling.providers.openai import OpenAIProvider


class GroqProvider(OpenAIProvider):
    """Provider adapter for Groq's HTTP and Batch APIs."""

    name = "groq"
    hostnames = ("api.groq.com",)
    batchable_endpoints = (
        "/openai/v1/chat/completions",
        "/openai/v1/audio/transcriptions",
        "/openai/v1/audio/translations",
    )
    file_upload_endpoint = "/openai/v1/files"
    file_content_endpoint = "/openai/v1/files/{id}/content"
    batch_endpoint = "/openai/v1/batches"

    def build_poll_request_spec(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        batch_id: str,
    ) -> ProviderRequestSpec:
        """
        Build Groq poll request metadata.
        """
        return super().build_poll_request_spec(
            base_url=base_url,
            api_headers=api_headers,
            batch_id=batch_id,
        )

    async def parse_poll_response(
        self,
        *,
        payload: dict[str, t.Any],
    ) -> PollSnapshot:
        """
        Parse Groq poll payload into normalized snapshot.
        """
        return await super().parse_poll_response(payload=payload)

    def build_results_request_spec(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        file_id: str | None,
        batch_id: str,
    ) -> ProviderRequestSpec:
        """
        Build Groq results request metadata.
        """
        return super().build_results_request_spec(
            base_url=base_url,
            api_headers=api_headers,
            file_id=file_id,
            batch_id=batch_id,
        )

    def decode_results_content(
        self,
        *,
        batch_id: str,
        content: str,
    ) -> dict[str, httpx.Response]:
        """
        Decode Groq JSONL results into responses keyed by custom ID.
        """
        return super().decode_results_content(batch_id=batch_id, content=content)

    def build_resume_context(
        self,
        *,
        host: str,
        headers: dict[str, str] | None,
    ) -> ResumeContext:
        """
        Build Groq resumed-polling context.
        """
        return super().build_resume_context(host=host, headers=headers)

    @staticmethod
    def _strip_openai_prefix(*, path: str) -> str:
        """
        Remove Groq's OpenAI compatibility prefix from request paths.

        Parameters
        ----------
        path : str
            Request path potentially prefixed with ``/openai``.

        Returns
        -------
        str
            Canonical provider path without the ``/openai`` prefix.
        """
        if path.startswith("/openai/"):
            return path[len("/openai") :]
        return path

    def build_jsonl_lines(
        self,
        *,
        requests: t.Sequence[PendingRequestLike],
    ) -> list[dict[str, t.Any]]:
        """
        Build JSONL lines with canonical endpoint URLs for Groq batches.

        Parameters
        ----------
        requests : typing.Sequence[PendingRequestLike]
            Pending requests to serialize.

        Returns
        -------
        list[dict[str, typing.Any]]
            JSONL lines with ``url`` normalized to ``/v1/...``.
        """
        jsonl_lines = super().build_jsonl_lines(requests=requests)
        for line in jsonl_lines:
            line["url"] = self._strip_openai_prefix(path=line["url"])
        return jsonl_lines

    async def build_file_based_batch_payload(
        self,
        *,
        file_id: str,
        endpoint: str,
        queue_key: tuple[str, str, str],
    ) -> dict[str, t.Any]:
        """
        Build Groq batch payload using canonical endpoint paths.

        Parameters
        ----------
        file_id : str
            Uploaded provider file ID.
        endpoint : str
            Queue endpoint path.
        queue_key : tuple[str, str, str]
            Queue identity tuple.

        Returns
        -------
        dict[str, typing.Any]
            File-based batch payload with normalized endpoint.
        """
        return await super().build_file_based_batch_payload(
            file_id=file_id,
            endpoint=self._strip_openai_prefix(path=endpoint),
            queue_key=queue_key,
        )
