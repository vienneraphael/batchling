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


class TogetherBatchTerminalStates(StrEnum):
    SUCCESS = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class TogetherProvider(BaseProvider):
    """Provider adapter for OpenAI's HTTP and Batch APIs."""

    name = "together"
    hostname = "api.together.xyz"
    batchable_endpoints = (
        "/v1/chat/completions",
        "/v1/audio/transcriptions",
    )
    file_upload_endpoint = "/v1/files/upload"
    file_content_endpoint = "/v1/files/{id}/content"
    batch_endpoint = "/v1/batches"
    batch_terminal_states: type[BatchTerminalStatesLike] = TogetherBatchTerminalStates
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
        Build Together poll request metadata.
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
        Parse Together poll payload into normalized snapshot.
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
        Build Together results request metadata.
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
        Decode Together JSONL results into responses keyed by custom ID.
        """
        return super().decode_results_content(batch_id=batch_id, content=content)

    def build_resume_context(
        self,
        *,
        host: str,
        headers: dict[str, str] | None,
    ) -> ResumeContext:
        """
        Build Together resumed-polling context.
        """
        return super().build_resume_context(host=host, headers=headers)

    def _build_batch_file_data_payload(self) -> dict[str, str]:
        """
        Build a batch file data payload for the provider.
        """
        return {
            "file_name": "batch.jsonl",
            "purpose": "batch-api",
        }

    def _get_batch_id_from_response(self, *, response_json: dict) -> str:
        """
        Get the batch ID from the response.
        """
        return response_json["job"]["id"]
