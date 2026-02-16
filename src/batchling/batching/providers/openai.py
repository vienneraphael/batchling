import typing as t
from enum import StrEnum

from batchling.batching.providers.base import (
    BaseProvider,
    BatchTerminalStatesLike,
)


class OpenAIBatchPayload(t.TypedDict):
    input_file_id: str
    endpoint: str
    completion_window: t.Literal["24h"]
    metadata: dict[str, str]


class OpenAIBatchTerminalStates(StrEnum):
    SUCCESS = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


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
    file_upload_endpoint = "/v1/files"
    file_content_endpoint = "/v1/files/{id}/content"
    batch_endpoint = "/v1/batches"
    batch_payload_type: type[OpenAIBatchPayload] = OpenAIBatchPayload
    batch_terminal_states: type[BatchTerminalStatesLike] = OpenAIBatchTerminalStates
    output_file_field_name: str = "output_file_id"
    error_file_field_name: str = "error_file_id"
