import os
import typing as t
from functools import cached_property

from openai import OpenAI
from openai.types.batch import Batch
from openai.types.file_object import FileObject
from pydantic import Field, computed_field

from batchling.experiment import Experiment
from batchling.file_utils import read_jsonl_file
from batchling.request import OpenAIBody, OpenAIRequest


class OpenAIExperiment(Experiment):
    body_cls: type[OpenAIBody] = Field(
        default=OpenAIBody, description="body class to use", init=False
    )
    request_cls: type[OpenAIRequest] = Field(
        default=OpenAIRequest, description="request class to use", init=False
    )

    @computed_field(repr=False)
    @cached_property
    def client(self) -> OpenAI:
        """Get the client

        Returns:
            OpenAI: The client
        """
        return OpenAI(api_key=os.getenv(self.api_key_name))

    def retrieve_provider_file(self):
        return self.client.files.retrieve(self.input_file_id)

    def retrieve_provider_batch(self):
        return self.client.batches.retrieve(self.batch_id)

    @computed_field
    @property
    def input_file(self) -> FileObject | None:
        if self.input_file_id is None:
            return None
        return self.retrieve_provider_file()

    @computed_field
    @property
    def batch(self) -> Batch | None:
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
        "validating",
        "failed",
        "in_progress",
        "finalizing",
        "completed",
        "expired",
        "cancelling",
        "cancelled",
    ]:
        if self.batch_id is None:
            if self.is_setup:
                return "setup"
            return "created"
        return self.batch.status

    def create_provider_file(self) -> str:
        return self.client.files.create(file=open(self.input_file_path, "rb"), purpose="batch").id

    def delete_provider_file(self):
        self.client.files.delete(file_id=self.input_file_id)

    def create_provider_batch(self) -> str:
        return self.client.batches.create(
            input_file_id=self.input_file_id,
            endpoint=self.endpoint,
            completion_window="24h",
            metadata={"description": self.description},
        ).id

    def raise_not_in_running_status(self):
        if self.status != "running":
            raise ValueError(f"Experiment in status {self.status} is not in running status")

    def raise_not_in_completed_status(self):
        if self.status != "completed":
            raise ValueError(f"Experiment in status {self.status} is not in completed status")

    def cancel_provider_batch(self):
        self.client.batches.cancel(self.batch_id)

    def delete_provider_batch(self):
        if self.batch.status == "in_progress":
            self.cancel_provider_batch()
        elif self.batch.status == "completed" and self.batch.output_file_id:
            self.delete_provider_file()

    def get_provider_results(self) -> list[dict]:
        with open(self.output_file_path, "w") as f:
            f.write(self.client.files.content(file_id=self.batch.output_file_id).text)
        return read_jsonl_file(self.output_file_path)
