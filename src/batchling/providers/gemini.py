import json
import os
import typing as t
from functools import cached_property

from google.genai import Client
from google.genai.types import BatchJob, File, UploadFileConfig
from pydantic import Field, computed_field

from batchling.experiment import Experiment
from batchling.request import GeminiBody, GeminiRequest


class GeminiExperiment(Experiment):
    body_cls: t.Type[GeminiBody] = Field(
        default=GeminiBody, description="body class to use", init=False
    )
    request_cls: t.Type[GeminiRequest] = Field(
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
            self.delete_provider_file(file_id=self.batch.output_file_id)

    def get_provider_results(self) -> list[dict]:
        output = json.loads(self.client.files.download(file=self.batch.dest.file_name))
        json.dump(obj=output, fp=open(self.output_file_path, "w"))
        return output
