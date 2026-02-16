import typing as t
from enum import StrEnum

from batchling.batching.providers.base import (
    BaseProvider,
    BatchTerminalStatesLike,
)


class TogetherBatchPayload(t.TypedDict):
    input_file_id: str
    endpoint: str
    completion_window: t.Literal["24h"]
    metadata: dict[str, str]


class TogetherBatchTerminalStates(StrEnum):
    SUCCESS = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class TogetherProvider(BaseProvider):
    """Provider adapter for OpenAI's HTTP and Batch APIs."""

    name = "together"
    hostnames = ("api.together.xyz",)
    batchable_endpoints = (
        "/v1/chat/completions",
        "/v1/audio/transcriptions",
    )
    file_upload_endpoint = "/v1/files/upload"
    file_content_endpoint = "/v1/files/{id}/content"
    batch_endpoint = "/v1/batches"
    batch_payload_type: type[TogetherBatchPayload] = TogetherBatchPayload
    batch_terminal_states: type[BatchTerminalStatesLike] = TogetherBatchTerminalStates
    output_file_field_name: str = "output_file_id"
    error_file_field_name: str = "error_file_id"

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
