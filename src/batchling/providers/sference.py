import json
import typing as t

import httpx

from batchling.providers.base import (
    PendingRequestLike,
    PollSnapshot,
    ProviderRequestSpec,
    ResumeContext,
)
from batchling.providers.openai import OpenAIProvider


class SferenceProvider(OpenAIProvider):
    """Provider adapter for sference's inline ``POST /v1/batches`` API."""

    name = "sference"
    hostname = "api.sference.com"
    is_file_based = False
    file_content_endpoint = "/v1/batches/{id}/results.jsonl"
    batch_endpoint = "/v1/batches"
    output_file_field_name: str = "id"
    error_file_field_name: str = "id"
    supported_completion_windows: tuple[str, ...] = ("24h",)
    batchable_endpoints = ("/v1/chat/completions",)

    def matches_url(self, hostname: str) -> bool:
        normalized = hostname.lower()
        return normalized in {"api.sference.com"}

    def build_jsonl_lines(
        self,
        *,
        requests: t.Sequence[PendingRequestLike],
    ) -> list[dict[str, t.Any]]:
        return [
            {
                "custom_id": request.custom_id,
                "body": json.loads(s=request.params["body"].decode(encoding="utf-8")),
            }
            for request in requests
        ]

    async def build_inline_batch_payload(
        self,
        *,
        jsonl_lines: list[dict[str, t.Any]],
        completion_window: str,
    ) -> dict[str, t.Any]:
        return {
            "window": completion_window,
            "requests": jsonl_lines,
        }

    def build_batch_results_path(self, *, file_id: str | None, batch_id: str) -> str:
        del file_id
        return f"/v1/batches/{batch_id}/results.jsonl"

    def get_progress_from_poll(
        self,
        *,
        payload: dict[str, t.Any],
        requests_count: int,
    ) -> tuple[int, float]:
        if payload.get(self.batch_status_field_name) == "completed":
            return requests_count, 100.0
        return 0, 0.0

    async def get_result_locator_from_poll_response(
        self,
        *,
        payload: dict[str, t.Any],
    ) -> str:
        return str(object=payload.get("id") or "")

    def build_poll_request_spec(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        batch_id: str,
    ) -> ProviderRequestSpec:
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
        return await super().parse_poll_response(
            payload=payload,
            requests_count=requests_count,
        )

    def build_results_request_spec(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        file_id: str | None,
        batch_id: str,
    ) -> ProviderRequestSpec:
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
        return super().decode_results_content(batch_id=batch_id, content=content)

    def from_batch_result(self, result_item: dict[str, t.Any]) -> httpx.Response:
        result_json = result_item.get("result_json")
        error_json = result_item.get("error_json")
        if result_json is not None:
            status_code = 200
            body: dict[str, t.Any] | t.Any = result_json
        elif error_json is not None:
            status_code = 500
            body = error_json
        else:
            status_code = 500
            body = {"error": result_item.get("status") or "Missing result"}

        content, content_headers = self.encode_body(body=body)
        headers = dict(content_headers)
        return httpx.Response(
            status_code=status_code,
            headers=headers,
            content=content,
        )

    def build_resume_context(
        self,
        *,
        host: str,
        headers: dict[str, str] | None,
    ) -> ResumeContext:
        return super().build_resume_context(host=host, headers=headers)
