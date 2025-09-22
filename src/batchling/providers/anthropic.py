import typing as t
from functools import cached_property

from pydantic import computed_field, field_validator

from batchling.experiment import Experiment
from batchling.request import AnthropicBody, AnthropicPart, AnthropicRequest, RawRequest
from batchling.utils.files import read_jsonl_file, write_jsonl_file

if t.TYPE_CHECKING:
    from anthropic import Anthropic
    from anthropic.types.messages import MessageBatch


class AnthropicExperiment(Experiment):
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

    @cached_property
    def client(self) -> "Anthropic":
        """Get the client

        Returns:
            Anthropic: The client
        """
        from anthropic import Anthropic

        return Anthropic(api_key=self.api_key)

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

    def retrieve_provider_file(self):
        return self.processed_file_path

    def retrieve_provider_batch(self):
        return self.client.messages.batches.retrieve(message_batch_id=self.batch_id)

    @property
    def provider_file(self) -> str | None:
        if self.provider_file_id is None:
            return None
        return self.processed_file_path

    @property
    def batch(self) -> t.Union["MessageBatch", None]:
        if self.batch_id is None:
            return None
        return self.retrieve_provider_batch()

    @property
    def status(
        self,
    ) -> t.Literal["created", "in_progress", "canceling", "ended"]:
        if self.batch_id is None:
            return "created"
        return self.batch.processing_status

    def create_provider_file(self) -> str:
        return self.processed_file_path

    def delete_provider_file(self):
        pass

    def create_provider_batch(self) -> str:
        from anthropic.types.message_create_params import (
            MessageCreateParamsNonStreaming,
        )
        from anthropic.types.messages.batch_create_params import Request

        data = read_jsonl_file(self.processed_file_path)
        requests = []
        for request in data:
            if "tools" in request["params"]:
                params = MessageCreateParamsNonStreaming(
                    model=self.model,
                    max_tokens=request["params"]["max_tokens"],
                    messages=request["params"]["messages"],
                    system=request["params"]["system"],
                    tools=request["params"]["tools"],
                    tool_choice=request["params"]["tool_choice"],
                )
            else:
                params = MessageCreateParamsNonStreaming(
                    model=self.model,
                    max_tokens=request["params"]["max_tokens"],
                    messages=request["params"]["messages"],
                    system=request["params"]["system"],
                )
            requests.append(Request(custom_id=request["custom_id"], params=params))
        return self.client.messages.batches.create(requests=requests).id

    def raise_not_in_running_status(self):
        if self.status not in ["in_progress"]:
            raise ValueError(f"Experiment in status {self.status} is not in in_progress status")

    def raise_not_in_completed_status(self):
        if self.status != "ended":
            raise ValueError(f"Experiment in status {self.status} is not in ended status")

    def cancel_provider_batch(self):
        self.client.messages.batches.cancel(message_batch_id=self.batch_id)

    def delete_provider_batch(self):
        if self.batch.processing_status in ["in_progress"]:
            self.cancel_provider_batch()
        elif self.batch.processing_status == "ended" and self.batch.results_url:
            self.client.messages.batches.delete(message_batch_id=self.batch_id)

    def get_provider_results(self) -> list[dict]:
        write_jsonl_file(
            file_path=self.results_file_path,
            data=[
                result.model_dump_json()
                for result in self.client.messages.batches.results(message_batch_id=self.batch_id)
            ],
        )
        return read_jsonl_file(self.results_file_path)
