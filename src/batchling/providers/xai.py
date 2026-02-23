import json
import typing as t
from enum import StrEnum

import httpx
from structlog import get_logger

from batchling.providers.base import (
    BaseProvider,
    BatchSubmission,
    BatchTerminalStatesLike,
    PendingRequestLike,
    PollSnapshot,
    ProviderRequestSpec,
    ResumeContext,
)

log = get_logger()


class XaiBatchTerminalStates(StrEnum):
    SUCCESS = "ended"


class XaiProvider(BaseProvider):
    """Provider adapter for OpenAI's HTTP and Batch APIs."""

    name = "xai"
    hostnames = ("api.x.ai",)
    batchable_endpoints = ("/v1/chat/completions",)
    file_upload_endpoint = "/v1/batches"
    file_content_endpoint = "/v1/batches/{id}/results"
    batch_endpoint = "/v1/batches"
    batch_terminal_states: type[BatchTerminalStatesLike] = XaiBatchTerminalStates
    batch_status_field_name: str = "state"
    output_file_field_name: str = "batch_id"
    error_file_field_name: str = "batch_id"
    custom_id_field_name: str = "batch_request_id"

    def build_poll_request_spec(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        batch_id: str,
    ) -> ProviderRequestSpec:
        """
        Build Xai poll request metadata.
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
        Parse XAI poll payload into normalized snapshot.
        """
        state = payload.get("state") or {}
        num_pending = state.get("num_pending") or 0
        num_completed = state.get("num_completed") or 0
        if num_pending > 0:
            if num_completed > 0:
                return PollSnapshot(
                    status="running",
                    output_file_id="",
                    error_file_id="",
                )
            return PollSnapshot(
                status="pending",
                output_file_id="",
                error_file_id="",
            )
        else:
            return PollSnapshot(
                status="ended",
                output_file_id="",
                error_file_id="",
            )

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
        Decode provider JSONL batch content into responses keyed by custom ID.

        Parameters
        ----------
        batch_id : str
            Batch ID for observability.
        content : str
            Raw JSONL content.

        Returns
        -------
        dict[str, httpx.Response]
            Responses keyed by provider custom ID.
        """
        decoded: dict[str, httpx.Response] = {}
        results = json.loads(s=content)
        for result in results.get("results") or []:
            custom_id = result.get(self.custom_id_field_name)
            if custom_id is None:
                log.debug(
                    event="Batch result missing custom_id",
                    provider=self.name,
                    batch_id=batch_id,
                )
                continue
            decoded[str(object=custom_id)] = self.from_batch_result(
                result_item=result.get("batch_result")
            )
        return decoded

    def build_resume_context(
        self,
        *,
        host: str,
        headers: dict[str, str] | None,
    ) -> ResumeContext:
        """
        Build Xai resumed-polling context.
        """
        return super().build_resume_context(host=host, headers=headers)

    def from_batch_result(self, result_item: dict[str, t.Any]) -> httpx.Response:
        """
        Convert Xai batch results into an ``httpx.Response``.

        Parameters
        ----------
        result_item : dict[str, typing.Any]
            Xai batch result JSON line.

        Returns
        -------
        httpx.Response
            HTTP response derived from the batch result.
        """
        log.debug(
            event="Decoding Xai batch results",
            result_item=result_item,
        )
        response = t.cast(dict[str, t.Any] | None, result_item.get("response"))
        if response:
            status_code = 200
            headers = dict(response.get("headers") or {})
            body = response
        else:
            status_code = 500
            headers = {}
            body = t.cast(
                dict[str, t.Any], result_item.get("error") or {"error": "Missing response"}
            )

        content, content_headers = self.encode_body(body=body)
        headers.update(content_headers)

        return httpx.Response(
            status_code=status_code,
            headers=headers,
            content=content,
        )

    def build_jsonl_lines(
        self,
        *,
        requests: t.Sequence[PendingRequestLike],
    ) -> list[dict[str, t.Any]]:
        """
        Build Xai JSONL lines.

        Parameters
        ----------
        requests : list[PendingRequestLike]
            Pending requests to serialize.

        Returns
        -------
        list[dict[str, typing.Any]]
            JSONL-ready request lines.
        """
        return [
            {
                "batch_request_id": request.custom_id,
                "batch_request": {
                    "chat_get_completion": json.loads(
                        s=request.params["body"].decode(encoding="utf-8"),
                    )
                },
            }
            for request in requests
        ]

    async def _create_batch_container(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> str:
        """
        Create a batch container.
        """
        data = {
            "name": "batchling runtime batch",
        }
        log.debug(
            event="Creating batch container",
            url=f"{base_url}{self.file_upload_endpoint}",
            headers={k: "***" for k in api_headers.keys()},
            json=data,
        )

        async with client_factory() as client:
            response = await client.post(
                url=f"{base_url}{self.file_upload_endpoint}",
                headers=api_headers,
                json=data,
            )
            response.raise_for_status()
            json_response = response.json()
        return json_response["batch_id"]

    async def _add_requests_to_batch(
        self,
        *,
        base_url: str,
        api_headers: dict[str, str],
        batch_id: str,
        jsonl_lines: list[dict[str, t.Any]],
        client_factory: t.Callable[[], httpx.AsyncClient],
    ) -> None:
        """
        Add requests to a batch.
        """
        log.debug(
            event="Adding requests to batch",
            url=f"{base_url}{self.file_upload_endpoint}/{batch_id}/requests",
            headers={k: "***" for k in api_headers.keys()},
            batch_id=batch_id,
            request_count=len(jsonl_lines),
        )
        async with client_factory() as client:
            response = await client.post(
                url=f"{base_url}{self.file_upload_endpoint}/{batch_id}/requests",
                headers=api_headers,
                json={"batch_requests": jsonl_lines},
            )
            response.raise_for_status()
        return

    async def process_batch(
        self,
        *,
        requests: t.Sequence[PendingRequestLike],
        client_factory: t.Callable[[], httpx.AsyncClient],
        queue_key: tuple[str, str, str],
    ) -> BatchSubmission:
        """
        Upload a JSONL file and create an OpenAI batch job.

        Parameters
        ----------
        requests : list[PendingRequestLike]
            Requests to submit in a single batch.
        client_factory : typing.Callable[[], httpx.AsyncClient]
            Async client factory for provider API calls.
        queue_key : tuple[str, str, str]
            Queue key associated with the current batch.

        Returns
        -------
        BatchSubmission
            Metadata required by the batch poller.
        """
        if not requests:
            raise ValueError("Cannot process an empty request batch")

        _, endpoint, _ = queue_key
        base_url = self._normalize_base_url(url=requests[0].params["url"])
        log.debug(
            event="Resolved batch submission target",
            provider=self.name,
            base_url=base_url,
            endpoint=endpoint,
            request_count=len(requests),
        )
        api_headers = self.build_api_headers(
            headers=requests[0].params.get("headers") or dict(),
        )
        api_headers = self.build_internal_headers(headers=api_headers)

        jsonl_lines = self.build_jsonl_lines(requests=requests)
        log.debug(
            event="Built JSONL lines",
            provider=self.name,
            request_count=len(jsonl_lines),
        )
        batch_id = await self._create_batch_container(
            base_url=base_url,
            api_headers=api_headers,
            client_factory=client_factory,
        )

        await self._add_requests_to_batch(
            base_url=base_url,
            api_headers=api_headers,
            batch_id=batch_id,
            jsonl_lines=jsonl_lines,
            client_factory=client_factory,
        )

        return BatchSubmission(
            base_url=base_url,
            api_headers=api_headers,
            batch_id=batch_id,
        )
