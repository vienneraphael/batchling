import os
import typing as t
from functools import cached_property

from groq import Groq
from groq.resources.batches import BatchRetrieveResponse
from groq.resources.files import FileInfoResponse
from pydantic import Field, computed_field

from batchling.experiment import Experiment
from batchling.file_utils import read_jsonl_file
from batchling.request import GroqBody, GroqRequest


class GroqExperiment(Experiment):
    body_cls: type[GroqBody] = Field(default=GroqBody, description="body class to use", init=False)
    request_cls: type[GroqRequest] = Field(
        default=GroqRequest, description="request class to use", init=False
    )

    @computed_field(repr=False)
    @cached_property
    def client(self) -> Groq:
        """Get the client

        Returns:
            Groq: The client
        """
        return Groq(api_key=os.getenv(self.api_key_name))

    def retrieve_provider_file(self):
        return self.client.files.info(file_id=self.input_file_id)

    def retrieve_provider_batch(self):
        return self.client.batches.retrieve(batch_id=self.batch_id)

    @computed_field
    @property
    def input_file(self) -> FileInfoResponse | None:
        if self.input_file_id is None:
            return None
        return self.retrieve_provider_file()

    @computed_field
    @property
    def batch(self) -> BatchRetrieveResponse | None:
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
            completion_window="24h",
            endpoint=self.endpoint,
            input_file_id=self.input_file_id,
            metadata={"description": self.description},
        ).id

    def raise_not_in_running_status(self):
        if self.status not in ["in_progress", "finalizing"]:
            raise ValueError(
                f"Experiment in status {self.status} is not in in_progress or finalizing status"
            )

    def raise_not_in_completed_status(self):
        if self.status != "completed":
            raise ValueError(f"Experiment in status {self.status} is not in completed status")

    def cancel_provider_batch(self):
        self.client.batches.cancel(batch_id=self.batch_id)

    def delete_provider_batch(self):
        if self.batch.status in ["in_progress", "finalizing"]:
            self.cancel_provider_batch()
        elif self.batch.status == "completed" and self.batch.output_file_id:
            self.delete_provider_file()

    def get_provider_results(self) -> list[dict]:
        output = self.client.files.content(file_id=self.batch.output_file_id)
        output.write_to_file(self.output_file_path)
        return read_jsonl_file(self.output_file_path)
