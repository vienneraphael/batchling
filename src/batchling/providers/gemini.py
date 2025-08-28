import os
import typing as t
from functools import cached_property

from google.genai import Client
from google.genai.types import BatchJob, File, UploadFileConfig
from pydantic import Field, computed_field

from batchling.batch_utils import (
    replace_placeholders,
    split_system_instructions_and_messages,
)
from batchling.experiment import Experiment
from batchling.file_utils import read_jsonl_file, write_jsonl_file
from batchling.request import (
    GeminiBody,
    GeminiConfig,
    GeminiMessage,
    GeminiPart,
    GeminiRequest,
    GeminiSystemInstruction,
)


class GeminiExperiment(Experiment):
    body_cls: type[GeminiBody] = Field(
        default=GeminiBody, description="body class to use", init=False
    )
    request_cls: type[GeminiRequest] = Field(
        default=GeminiRequest, description="request class to use", init=False
    )

    @computed_field(repr=False)
    @cached_property
    def client(self) -> Client:
        """Get the client

        Returns:
            Client: The client
        """
        return Client(api_key=os.getenv(self.api_key_name))

    def retrieve_provider_file(self):
        return self.client.files.get(name=self.input_file_id)

    def retrieve_provider_batch(self):
        return self.client.batches.get(name=self.batch_id)

    @computed_field
    @property
    def input_file(self) -> File | None:
        if self.input_file_id is None:
            return None
        return self.retrieve_provider_file()

    @computed_field
    @property
    def batch(self) -> BatchJob | None:
        if self.batch_id is None:
            return None
        return self.retrieve_provider_batch()

    @computed_field
    @property
    def status(
        self,
    ) -> t.Literal[
        "setup",
        "created",
        "JOB_STATE_UNSPECIFIED",
        "JOB_STATE_QUEUED",
        "JOB_STATE_PENDING",
        "JOB_STATE_RUNNING",
        "JOB_STATE_SUCCEEDED",
        "JOB_STATE_FAILED",
        "JOB_STATE_CANCELLING",
        "JOB_STATE_CANCELLED",
        "JOB_STATE_PAUSED",
        "JOB_STATE_EXPIRED",
        "JOB_STATE_UPDATING",
        "JOB_STATE_PARTIALLY_SUCCEEDED",
    ]:
        if self.batch_id is None:
            if self.is_setup:
                return "setup"
            return "created"
        return self.batch.state.name

    def create_provider_file(self) -> str:
        return self.client.files.upload(
            file=self.input_file_path,
            config=UploadFileConfig(
                display_name=self.input_file_path.split("/")[-1], mime_type="jsonl"
            ),
        ).name

    def delete_provider_file(self):
        self.client.files.delete(name=self.input_file_id)

    def create_provider_batch(self) -> str:
        return self.client.batches.create(
            model=self.model,
            src=self.input_file_id,
            config={"display_name": self.input_file_path.split("/")[-1]},
        ).name

    def raise_not_in_running_status(self):
        if self.status not in ["JOB_STATE_RUNNING", "JOB_STATE_PENDING"]:
            raise ValueError(
                f"Experiment in status {self.status} is not in JOB_STATE_RUNNING or JOB_STATE_PENDING status"
            )

    def raise_not_in_completed_status(self):
        if self.status != "JOB_STATE_SUCCEEDED":
            raise ValueError(
                f"Experiment in status {self.status} is not in JOB_STATE_SUCCEEDED status"
            )

    def cancel_provider_batch(self):
        self.client.batches.cancel(name=self.batch_id)

    def delete_provider_batch(self):
        if self.batch.status in ["JOB_STATE_RUNNING", "JOB_STATE_PENDING"]:
            self.cancel_provider_batch()
        elif self.batch.status == "JOB_STATE_SUCCEEDED" and self.batch.output_file_id:
            self.delete_provider_file()

    def write_input_batch_file(self) -> None:
        if self.placeholders is None:
            self.placeholders = []
        batch_requests = []
        for i, placeholder_dict in enumerate(self.placeholders):
            clean_messages = replace_placeholders(
                messages=self.template_messages, placeholder_dict=placeholder_dict
            )
            system_instructions, messages = split_system_instructions_and_messages(clean_messages)
            batch_request = GeminiRequest(
                key=f"{self.id}-sample-{i}",
                request=GeminiBody(
                    system_instruction=GeminiSystemInstruction(
                        parts=[GeminiPart(text=system_instructions["content"])]
                    )
                    if system_instructions
                    else None,
                    contents=[
                        GeminiMessage(
                            role=message["role"], parts=[GeminiPart(text=message["content"])]
                        )
                        for message in messages
                    ],
                    generation_config=GeminiConfig(
                        response_mime_type="application/json",
                        response_schema=self.response_format,
                    )
                    if self.response_format
                    else None,
                ),
            )
            batch_requests.append(batch_request.model_dump_json())
        write_jsonl_file(file_path=self.input_file_path, data=batch_requests)

    def get_provider_results(self) -> list[dict]:
        output = (
            self.client.files.download(file=self.batch.dest.file_name)
            .decode("utf-8")
            .strip("\n")
            .split("\n")
        )
        write_jsonl_file(file_path=self.output_file_path, data=output)
        return read_jsonl_file(file_path=self.output_file_path)
