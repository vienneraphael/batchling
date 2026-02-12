from enum import StrEnum

from batchling.batching.providers.base import (
    BaseProvider,
    BatchTerminalStatesLike,
)


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
    batch_endpoint = "/v1/batches"
    batch_terminal_states: type[BatchTerminalStatesLike] = OpenAIBatchTerminalStates
