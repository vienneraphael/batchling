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


class MistralBatchTerminalStates(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class MistralProvider(BaseProvider):
    """Provider adapter for Mistral's HTTP and Batch APIs."""

    name = "mistral"
    hostname = "api.mistral.ai"
    batchable_endpoints = (
        "/v1/chat/completions",
        "/v1/fim/completions",
        "/v1/embeddings",
        "/v1/moderations",
        "/v1/chat/moderations/v1/ocr",
        "/v1/classifications",
        "/v1/conversations/v1/audio/transcriptions",
    )
    file_upload_endpoint = "/v1/files"
    file_content_endpoint = "/v1/files/{id}/content"
    batch_endpoint = "/v1/batch/jobs"
    batch_terminal_states: type[BatchTerminalStatesLike] = MistralBatchTerminalStates
    output_file_field_name: str = "output_file"
    error_file_field_name: str = "error_file"

    def build_poll_request_spec(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        batch_id: str,
    ) -> ProviderRequestSpec:
        """
        Build Mistral poll request metadata.
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
        requests_count: int,
    ) -> PollSnapshot:
        """
        Parse Mistral poll payload into normalized snapshot.
        """
        return await super().parse_poll_response(
            payload=payload,
            requests_count=requests_count,
        )

    def get_progress_from_poll(
        self,
        *,
        payload: dict[str, t.Any],
        requests_count: int,
    ) -> tuple[int, float]:
        """
        Extract Mistral poll progress from ``completed_requests``.

        Parameters
        ----------
        payload : dict[str, typing.Any]
            Mistral poll payload.
        requests_count : int
            Total request count for this batch.

        Returns
        -------
        tuple[int, float]
            Completed requests and completion percent.
        """
        completed = max(0, self._coerce_int(value=payload.get("completed_requests", 0)))
        if requests_count > 0:
            percent = (completed / requests_count) * 100.0
        else:
            percent = 0.0
        return completed, percent

    def build_results_request_spec(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        file_id: str | None,
        batch_id: str,
    ) -> ProviderRequestSpec:
        """
        Build Mistral results request metadata.
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
        Decode Mistral JSONL results into responses keyed by custom ID.
        """
        return super().decode_results_content(batch_id=batch_id, content=content)

    def build_resume_context(
        self,
        *,
        host: str,
        headers: dict[str, str] | None,
    ) -> ResumeContext:
        """
        Build Mistral resumed-polling context.
        """
        return super().build_resume_context(host=host, headers=headers)

    async def build_file_based_batch_payload(
        self,
        *,
        file_id: str,
        endpoint: str,
        queue_key: tuple[str, str, str],
        completion_window: str,
    ) -> dict[str, t.Any]:
        """
        Build a batch payload for the provider.
        """
        _, _, model_name = queue_key
        return {
            "model": model_name,
            "input_files": [file_id],
            "endpoint": endpoint,
            "timeout_hours": int(completion_window.rstrip("h")),
            "metadata": {"description": "batchling runtime batch"},
        }
