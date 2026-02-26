import typing as t

import httpx

from batchling.providers.base import PollSnapshot, ProviderRequestSpec, ResumeContext
from batchling.providers.openai import OpenAIProvider


class DoublewordProvider(OpenAIProvider):
    """Provider adapter for Doubleword's OpenAI-compatible Batch API."""

    name = "doubleword"
    hostname = "api.doubleword.ai"
    batchable_endpoints = (
        "/v1/chat/completions",
        "/v1/responses",
        "/v1/embeddings",
        "/v1/moderations",
        "/v1/completions",
    )

    def build_poll_request_spec(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        batch_id: str,
    ) -> ProviderRequestSpec:
        """
        Build Doubleword poll request metadata.
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
        Parse Doubleword poll payload into normalized snapshot.
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
        Build Doubleword results request metadata.
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
        Decode Doubleword JSONL results into responses keyed by custom ID.
        """
        return super().decode_results_content(batch_id=batch_id, content=content)

    def build_resume_context(
        self,
        *,
        host: str,
        headers: dict[str, str] | None,
    ) -> ResumeContext:
        """
        Build Doubleword resumed-polling context.
        """
        return super().build_resume_context(host=host, headers=headers)
