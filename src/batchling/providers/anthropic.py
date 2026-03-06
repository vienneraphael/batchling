import json
import typing as t
from enum import StrEnum

import httpx

from batchling.providers.base import (
    BaseProvider,
    BatchTerminalStatesLike,
    PendingRequestLike,
    PollSnapshot,
    ProviderRequestSpec,
    ResumeContext,
)


class AnthropicBatchTerminalStates(StrEnum):
    SUCCESS = "ended"


class AnthropicProvider(BaseProvider):
    """Provider adapter for OpenAI's HTTP and Batch APIs."""

    name = "anthropic"
    hostname = "api.anthropic.com"
    batchable_endpoints = ("/v1/messages",)
    is_file_based = False
    file_content_endpoint = "/v1/messages/batches/{id}/results"
    batch_endpoint = "/v1/messages/batches"
    batch_terminal_states: type[BatchTerminalStatesLike] = AnthropicBatchTerminalStates
    batch_status_field_name: str = "processing_status"
    output_file_field_name: str = "id"
    error_file_field_name: str = "id"

    def build_poll_request_spec(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        batch_id: str,
    ) -> ProviderRequestSpec:
        """
        Build Anthropic poll request metadata.
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
        Parse Anthropic poll payload into normalized snapshot.
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
        Extract Anthropic poll progress from ``request_counts.succeeded``.

        Parameters
        ----------
        payload : dict[str, typing.Any]
            Anthropic poll payload.
        requests_count : int
            Total request count for this batch.

        Returns
        -------
        tuple[int, float]
            Completed requests and completion percent.
        """
        request_counts = payload.get("request_counts") or {}
        completed = max(0, self._coerce_int(value=request_counts.get("succeeded", 0)))
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
        Build Anthropic results request metadata.
        """
        del base_url
        del file_id
        return ProviderRequestSpec(
            method="GET",
            path=self.file_content_endpoint.format(id=batch_id),
            headers=api_headers,
        )

    def decode_results_content(
        self,
        *,
        batch_id: str,
        content: str,
    ) -> dict[str, httpx.Response]:
        """
        Decode Anthropic JSONL results into responses keyed by custom ID.
        """
        return super().decode_results_content(batch_id=batch_id, content=content)

    def build_resume_context(
        self,
        *,
        host: str,
        headers: dict[str, str] | None,
    ) -> ResumeContext:
        """
        Build Anthropic resumed-polling context.
        """
        return super().build_resume_context(host=host, headers=headers)

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
