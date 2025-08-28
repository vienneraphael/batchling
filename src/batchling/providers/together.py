import os
import typing as t
from functools import cached_property

from pydantic import Field, computed_field
from together import Together
from together.resources.batch import BatchJob
from together.resources.files import FileResponse

from batchling.experiment import Experiment
from batchling.file_utils import read_jsonl_file
from batchling.request import TogetherBody, TogetherRequest


class TogetherExperiment(Experiment):
    body_cls: type[TogetherBody] = Field(
        default=TogetherBody, description="body class to use", init=False
    )
    request_cls: type[TogetherRequest] = Field(
        default=TogetherRequest, description="request class to use", init=False
    )

    @computed_field(repr=False)
    @cached_property
    def client(self) -> Together:
        """Get the client

        Returns:
            Together: The client
        """
        return Together(api_key=os.getenv(self.api_key_name))

    def retrieve_provider_file(self):
        return self.client.files.retrieve(id=self.input_file_id)

    def retrieve_provider_batch(self):
        return self.client.batches.get_batch(batch_job_id=self.batch_id)

    @computed_field
    @property
    def input_file(self) -> FileResponse | None:
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
        "VALIDATING",
        "IN_PROGRESS",
        "COMPLETED",
        "FAILED",
        "EXPIRED",
        "CANCELLED",
    ]:
        if self.batch_id is None:
            if self.is_setup:
                return "setup"
            return "created"
        return self.batch.status

    def create_provider_file(self) -> str:
        return self.client.files.upload(file=self.input_file_path, purpose="batch-api").id

    def delete_provider_file(self):
        self.client.files.delete(id=self.input_file_id)

    def create_provider_batch(self) -> str:
        return self.client.batches.create_batch(
            file_id=self.input_file_id,
            endpoint=self.endpoint,
        ).id

    def raise_not_in_running_status(self):
        if self.status not in ["IN_PROGRESS", "VALIDATING"]:
            raise ValueError(
                f"Experiment in status {self.status} is not in IN_PROGRESS or VALIDATING status"
            )

    def raise_not_in_completed_status(self):
        if self.status != "COMPLETED":
            raise ValueError(f"Experiment in status {self.status} is not in COMPLETED status")

    def cancel_provider_batch(self):
        self.client.batches.cancel_batch(batch_job_id=self.batch_id)

    def delete_provider_batch(self):
        if self.batch.status in ["IN_PROGRESS", "VALIDATING"]:
            self.cancel_provider_batch()
        elif self.batch.status == "COMPLETED" and self.batch.output_file_id:
            self.delete_provider_file()

    def get_provider_results(self) -> list[dict]:
        self.client.files.retrieve_content(
            id=self.batch.output_file_id, output=self.output_file_path
        )
        return read_jsonl_file(self.output_file_path)
