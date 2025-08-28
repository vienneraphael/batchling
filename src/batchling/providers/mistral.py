import os
import typing as t
from functools import cached_property

from mistralai import Mistral
from mistralai.models import BatchJobOut, RetrieveFileOut
from pydantic import Field, computed_field

from batchling.experiment import Experiment
from batchling.file_utils import read_jsonl_file
from batchling.request import MistralBody, MistralRequest


class MistralExperiment(Experiment):
    body_cls: type[MistralBody] = Field(
        default=MistralBody, description="body class to use", init=False
    )
    request_cls: type[MistralRequest] = Field(
        default=MistralRequest, description="request class to use", init=False
    )

    @computed_field(repr=False)
    @cached_property
    def client(self) -> Mistral:
        """Get the client

        Returns:
            Mistral: The client
        """
        return Mistral(api_key=os.getenv(self.api_key_name))

    def retrieve_provider_file(self):
        return self.client.files.retrieve(file_id=self.input_file_id)

    def retrieve_provider_batch(self):
        return self.client.batch.jobs.get(job_id=self.batch_id)

    @computed_field
    @property
    def input_file(self) -> RetrieveFileOut | None:
        if self.input_file_id is None:
            return None
        return self.retrieve_provider_file()

    @computed_field
    @property
    def batch(self) -> BatchJobOut | None:
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
        "QUEUED",
        "RUNNING",
        "SUCCESS",
        "FAILED",
        "TIMEOUT_EXCEEDED",
        "CANCELLATION_REQUESTED",
        "CANCELLED",
    ]:
        if self.batch_id is None:
            if self.is_setup:
                return "setup"
            return "created"
        return self.batch.status

    def create_provider_file(self) -> str:
        return self.client.files.upload(
            file={
                "file_name": self.input_file_path.split("/")[-1],
                "content": open(self.input_file_path, "rb"),
            },
            purpose="batch",
        ).id

    def delete_provider_file(self):
        self.client.files.delete(file_id=self.input_file_id)

    def create_provider_batch(self) -> str:
        return self.client.batch.jobs.create(
            input_files=[self.input_file_id],
            endpoint=self.endpoint,
            model=self.model,
            metadata={"description": self.description},
        ).id

    def raise_not_in_running_status(self):
        if self.status not in ["QUEUED", "RUNNING"]:
            raise ValueError(
                f"Experiment in status {self.status} is not in QUEUED or RUNNING status"
            )

    def raise_not_in_completed_status(self):
        if self.status != "SUCCESS":
            raise ValueError(f"Experiment in status {self.status} is not in SUCCESS status")

    def cancel_provider_batch(self):
        self.client.batch.jobs.cancel(job_id=self.batch_id)

    def delete_provider_batch(self):
        if self.batch.status in ["QUEUED", "RUNNING"]:
            self.cancel_provider_batch()
        elif self.batch.status == "SUCCESS" and self.batch.output_file_id:
            self.delete_provider_file()

    def get_provider_results(self) -> list[dict]:
        output = self.client.files.download(file_id=self.batch.output_file)
        with open(self.output_file_path, "w") as f:
            for chunk in output.stream:
                f.write(chunk.decode("utf-8"))
        return read_jsonl_file(self.output_file_path)
