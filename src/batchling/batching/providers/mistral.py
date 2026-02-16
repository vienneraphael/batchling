import typing as t
from enum import StrEnum

from batchling.batching.providers.base import (
    BaseProvider,
    BatchTerminalStatesLike,
)


class MistralBatchPayload(t.TypedDict):
    model: str
    input_files: list[str]
    endpoint: str
    timeout_hours: int
    metadata: dict[str, str]


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
    batch_endpoint = "/v1/batch/jobs"
    batch_payload_type: type[MistralBatchPayload] = MistralBatchPayload
    batch_terminal_states: type[BatchTerminalStatesLike] = MistralBatchTerminalStates
    output_file_field_name: str = "output_file"
    error_file_field_name: str = "error_file"

    async def _build_batch_payload(
        self,
        *,
        file_id: str,
        endpoint: str,
        queue_key: tuple[str, str, str],
    ) -> t.Mapping[str, t.Any]:
        """
        Build a batch payload for the provider.
        """
        _, _, model_name = queue_key
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("Mistral homogeneous batch requires model name in queue key")
        return self.batch_payload_type(
            model=model_name,
            input_files=[file_id],
            endpoint=endpoint,
            timeout_hours=24,
            metadata={"description": "batchling runtime batch"},
        )
