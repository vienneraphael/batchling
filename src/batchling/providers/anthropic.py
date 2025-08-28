import os
import typing as t
from functools import cached_property

from anthropic import Anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages import MessageBatch
from anthropic.types.messages.batch_create_params import Request
from pydantic import Field, computed_field, field_validator

from batchling.batch_utils import (
    replace_placeholders,
    split_system_instructions_and_messages,
)
from batchling.experiment import Experiment
from batchling.file_utils import read_jsonl_file, write_jsonl_file
from batchling.request import AnthropicBody, AnthropicPart, AnthropicRequest, Message


class AnthropicExperiment(Experiment):
    body_cls: type[AnthropicBody] = Field(
        default=AnthropicBody, description="body class to use", init=False
    )
    request_cls: type[AnthropicRequest] = Field(
        default=AnthropicRequest, description="request class to use", init=False
    )
    max_tokens_per_request: int = Field(description="max tokens to use per request")

    @field_validator("max_tokens_per_request", mode="before")
    @classmethod
    def check_max_tokens_per_request_not_none(cls, value: int | None) -> int:
        if value is None:
            raise ValueError(
                "max_tokens_per_request is required to be set for Anthropic experiments and cannot be None"
            )
        if value <= 0:
            raise ValueError("max_tokens_per_request must be a positive integer")
        return value

    @computed_field(repr=False)
    @cached_property
    def client(self) -> Anthropic:
        """Get the client

        Returns:
            Anthropic: The client
        """
        return Anthropic(api_key=os.getenv(self.api_key_name))

    def retrieve_provider_file(self):
        return self.input_file_path

    def retrieve_provider_batch(self):
        return self.client.messages.batches.retrieve(message_batch_id=self.batch_id)

    @computed_field
    @property
    def input_file(self) -> str | None:
        if self.input_file_id is None:
            return None
        return self.input_file_path

    @computed_field
    @property
    def batch(self) -> MessageBatch | None:
        if self.batch_id is None:
            return None
        return self.retrieve_provider_batch()

    @computed_field
    @property
    def status(
        self,
    ) -> t.Literal["setup", "created", "in_progress", "canceling", "ended"]:
        if self.batch_id is None:
            if self.is_setup:
                return "setup"
            return "created"
        return self.batch.processing_status

    def create_provider_file(self) -> str:
        return self.input_file_path

    def delete_provider_file(self):
        pass

    def write_input_batch_file(self) -> None:
        if self.placeholders is None:
            self.placeholders = []
        batch_requests = []
        for i, placeholder_dict in enumerate(self.placeholders):
            clean_messages = replace_placeholders(
                messages=self.template_messages, placeholder_dict=placeholder_dict
            )
            system_dict, messages = split_system_instructions_and_messages(messages=clean_messages)
            system_instructions = (
                [AnthropicPart(type="text", text=system_dict["content"])] if system_dict else None
            )
            messages = [
                Message(role=message["role"], content=message["content"]) for message in messages
            ]
            batch_request = AnthropicRequest(
                custom_id=f"{self.id}-sample-{i}",
                params=AnthropicBody(
                    model=self.model,
                    messages=messages,
                    system=system_instructions,
                    max_tokens=self.max_tokens_per_request,
                ),
            )
            batch_requests.append(batch_request.model_dump_json(exclude_none=True))
        write_jsonl_file(file_path=self.input_file_path, data=batch_requests)

    def create_provider_batch(self) -> str:
        data = read_jsonl_file(self.input_file_path)
        return self.client.messages.batches.create(
            requests=[
                Request(
                    custom_id=request.get("custom_id"),
                    params=MessageCreateParamsNonStreaming(
                        model=self.model,
                        messages=request["params"]["messages"],
                        system=request["params"]["system"],
                        max_tokens=request["params"]["max_tokens"],
                    ),
                )
                for request in data
            ]
        ).id

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
        output = [
            result.model_dump_json()
            for result in self.client.messages.batches.results(message_batch_id=self.batch_id)
        ]
        write_jsonl_file(file_path=self.output_file_path, data=output)
        return output
