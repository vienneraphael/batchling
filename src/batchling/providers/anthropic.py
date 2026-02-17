import json
import typing as t
from enum import StrEnum

import httpx

from batchling.providers.base import (
    BaseProvider,
    BatchTerminalStatesLike,
    PendingRequestLike,
)


class AnthropicBatchTerminalStates(StrEnum):
    SUCCESS = "ended"


class AnthropicProvider(BaseProvider):
    """Provider adapter for OpenAI's HTTP and Batch APIs."""

    name = "anthropic"
    hostnames = ("api.anthropic.com",)
    batchable_endpoints = ("/v1/messages",)
    is_file_based = False
    file_content_endpoint = "/v1/messages/batches/{id}/results"
    batch_endpoint = "/v1/messages/batches"
    batch_terminal_states: type[BatchTerminalStatesLike] = AnthropicBatchTerminalStates
    batch_status_field_name: str = "processing_status"
    output_file_field_name: str = "id"
    error_file_field_name: str = "id"

    def build_jsonl_lines(
        self,
        *,
        requests: t.Sequence[PendingRequestLike],
    ) -> list[dict[str, t.Any]]:
        """
        Build provider batch-file JSONL lines.

        Parameters
        ----------
        requests : list[PendingRequestLike]
            Pending requests to serialize.

        Returns
        -------
        list[dict[str, typing.Any]]
            JSONL-ready request lines.
        """
        jsonl_lines = []
        for request in requests:
            body = json.loads(s=request.params["body"].decode(encoding="utf-8"))
            jsonl_lines.append(
                {
                    "custom_id": request.custom_id,
                    "params": {
                        "model": body["model"],
                        "max_tokens": body["max_tokens"],
                        "messages": body["messages"],
                    },
                }
            )
        return jsonl_lines

    def from_batch_result(self, result_item: dict[str, t.Any]) -> httpx.Response:
        """
        Convert Anthropic batch results into an ``httpx.Response``.

        Parameters
        ----------
        result_item : dict[str, typing.Any]
            Anthropic batch result JSON line.

        Returns
        -------
        httpx.Response
            HTTP response derived from the batch result.
        """
        result = t.cast(dict[str, t.Any], result_item.get("result") or {})
        response = t.cast(dict[str, t.Any] | None, result.get("message"))
        if response:
            status_code = 200
            headers = dict(response.get("headers") or {})
            body = response
        else:
            status_code = 500
            headers = {}
            body = t.cast(dict[str, t.Any], result.get("error") or {"error": "Missing response"})

        content, content_headers = self.encode_body(body=body)
        headers.update(content_headers)

        return httpx.Response(
            status_code=status_code,
            headers=headers,
            content=content,
        )
