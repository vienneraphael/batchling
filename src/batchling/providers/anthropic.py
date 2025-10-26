import typing as t
from functools import cached_property

from pydantic import computed_field, field_validator

from batchling.experiment import Experiment
from batchling.models import ProviderBatch, ProviderFile
from batchling.request import AnthropicBody, AnthropicPart, AnthropicRequest, RawRequest
from batchling.utils.files import read_jsonl_file


class AnthropicExperiment(Experiment):
    BASE_URL: str = "https://api.anthropic.com/v1/messages/batches"

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}

    @field_validator("raw_requests", mode="before")
    @classmethod
    def check_raw_requests_not_none(cls, value: list[RawRequest] | None) -> list[RawRequest] | None:
        if value is None:
            return None
        if any(request.max_tokens is None for request in value):
            raise ValueError(
                "max_tokens is required to be set for each request for Anthropic experiments and cannot be None"
            )
        return value

    @computed_field
    @cached_property
    def processed_requests(self) -> list[AnthropicRequest]:
        processed_requests: list[AnthropicRequest] = []
        for i, raw_request in enumerate(self.raw_requests):
            processed_requests.append(
                AnthropicRequest(
                    custom_id=f"{self.name}-sample-{i}",
                    params=AnthropicBody(
                        model=self.model,
                        max_tokens=raw_request.max_tokens,
                        messages=raw_request.messages,
                        tools=[
                            {
                                "name": "structured_output",
                                "description": "Output a structured response",
                                "input_schema": self.response_format["json_schema"]["schema"],
                            }
                        ]
                        if self.response_format
                        else None,
                        tool_choice={"type": "tool", "name": "structured_output"}
                        if self.response_format
                        else None,
                        system=[AnthropicPart(type="text", text=raw_request.system_prompt)],
                    ),
                )
            )
        return processed_requests

    def retrieve_provider_file(self) -> ProviderFile | str:
        # Anthropic does not expose file objects; we return the local path
        return self.processed_file_path

    def retrieve_provider_batch(self) -> ProviderBatch | None:
        data = self._http_get_json(f"{self.BASE_URL}/{self.batch_id}")
        return ProviderBatch.model_validate(data)

    @property
    def provider_file(self) -> ProviderFile | str | None:
        if self.provider_file_id is None:
            return None
        return self.processed_file_path

    @property
    def batch(self) -> ProviderBatch | None:
        if self.batch_id is None:
            return None
        return self.retrieve_provider_batch()

    @property
    def status(
        self,
    ) -> t.Literal["created", "in_progress", "canceling", "ended"]:
        if self.batch_id is None:
            return "created"
        return self.batch.status

    def create_provider_file(self) -> str:
        return self.processed_file_path

    def delete_provider_file(self):
        pass

    def create_provider_batch(self) -> str:
        data = read_jsonl_file(self.processed_file_path)
        request_list = []
        for request in data:
            request["params"]["model"] = self.model
            request_list.append(request)
        response = self._http_post_json(
            f"{self.BASE_URL}",
            json={
                "requests": request_list,
            },
        )
        return ProviderBatch.model_validate(response).id

    def raise_not_in_running_status(self):
        if self.status not in ["in_progress"]:
            raise ValueError(f"Experiment in status {self.status} is not in in_progress status")

    def raise_not_in_completed_status(self):
        if self.status != "ended":
            raise ValueError(f"Experiment in status {self.status} is not in ended status")

    def cancel_provider_batch(self) -> None:
        self._http_post_json(f"{self.BASE_URL}/{self.batch_id}/cancel")

    def delete_provider_batch(self) -> None:
        batch = self.batch
        if batch is None:
            return
        if batch.status in ["in_progress"]:
            self.cancel_provider_batch()
        elif batch.status == "ended" and batch.output_file_id:
            self._http_delete(f"{self.BASE_URL}/{self.batch_id}")

    def get_provider_results(self) -> list[dict]:
        batch = self.batch
        if batch and batch.output_file_id:
            return self._download_results(batch.output_file_id)
        return []
