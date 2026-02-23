import typing as t
from enum import StrEnum

import httpx

from batchling.providers.base import (
    BaseProvider,
    BatchTerminalStatesLike,
    PollSnapshot,
    ProviderRequestSpec,
    ResumeContext,
)


class CerebrasBatchTerminalStates(StrEnum):
    SUCCESS = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CerebrasProvider(BaseProvider):
    """Provider adapter for OpenAI's HTTP and Batch APIs."""

    name = "cerebras"
    hostnames = ("api.cerebras.ai",)
    batchable_endpoints = ("/v1/chat/completions",)
    file_upload_endpoint = "/v1/files"
    file_content_endpoint = "/v1/files/{id}/content"
    batch_endpoint = "/v1/batches"
    batch_terminal_states: type[BatchTerminalStatesLike] = CerebrasBatchTerminalStates
    output_file_field_name: str = "output_file_id"
    error_file_field_name: str = "error_file_id"

    def build_poll_request_spec(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        batch_id: str,
    ) -> ProviderRequestSpec:
        """
        Build Cerebras poll request metadata.
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
        Parse Cerebras poll payload into normalized snapshot.
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
        Build Cerebras results request metadata.
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
        Decode Cerebras JSONL results into responses keyed by custom ID.
        """
        return super().decode_results_content(batch_id=batch_id, content=content)

    def build_resume_context(
        self,
        *,
        host: str,
        headers: dict[str, str] | None,
    ) -> ResumeContext:
        """
        Build Cerebras resumed-polling context.
        """
        return super().build_resume_context(host=host, headers=headers)
