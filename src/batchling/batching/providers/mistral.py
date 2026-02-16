import typing as t
from enum import StrEnum

from batchling.batching.providers.base import (
    BaseProvider,
    BatchTerminalStatesLike,
)


class MistralBatchTerminalStates(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class MistralProvider(BaseProvider):
    """Provider adapter for Mistral's HTTP and Batch APIs."""

    name = "mistral"
    hostnames = ("api.mistral.ai",)
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
        _, _, model_name = queue_key
        return {
            "model": model_name,
            "input_files": [file_id],
            "endpoint": endpoint,
            "timeout_hours": 24,
            "metadata": {"description": "batchling runtime batch"},
        }
