import typing as t
from functools import cached_property

from pydantic import computed_field

from batchling.experiment import Experiment
from batchling.request import ProcessedMessage, TogetherBody, TogetherRequest
from batchling.utils.files import read_jsonl_file

if t.TYPE_CHECKING:
    from together import Together
    from together.resources.batch import BatchJob
    from together.resources.files import FileResponse


class TogetherExperiment(Experiment):
    @cached_property
    def client(self) -> "Together":
        """Get the client

        Returns:
            Together: The client
        """
        from together import Together

        return Together(api_key=self.api_key)

    @computed_field
    @cached_property
    def processed_requests(self) -> list[TogetherRequest]:
        processed_requests: list[TogetherRequest] = []
        for i, raw_request in enumerate(self.raw_requests):
            messages: list[ProcessedMessage] = []
            if raw_request.system_prompt is not None:
                messages.append(ProcessedMessage(role="system", content=raw_request.system_prompt))
            messages.extend(
                [
                    ProcessedMessage(role=message.role, content=message.content)
                    for message in raw_request.messages
                ]
            )
            processed_requests.append(
                TogetherRequest(
                    custom_id=f"{self.name}-sample-{i}",
                    body=TogetherBody(
                        messages=messages,
                        max_tokens=raw_request.max_tokens,
                        model=self.model,
                        response_format=self.response_format,
                    ),
                )
            )
        return processed_requests

    def retrieve_provider_file(self):
        return self.client.files.retrieve(id=self.provider_file_id)

    def retrieve_provider_batch(self):
        return self.client.batches.get_batch(batch_job_id=self.batch_id)

    @property
    def provider_file(self) -> t.Union["FileResponse", None]:
        if self.provider_file_id is None:
            return None
        return self.retrieve_provider_file()

    @property
    def batch(self) -> t.Union["BatchJob", None]:
        if self.batch_id is None:
            return None
        return self.retrieve_provider_batch()

    @property
    def status(
        self,
    ) -> t.Literal[
        "created",
        "VALIDATING",
        "IN_PROGRESS",
        "COMPLETED",
        "FAILED",
        "EXPIRED",
        "CANCELLED",
    ]:
        if self.batch_id is None:
            return "created"
        return self.batch.status

    def create_provider_file(self) -> str:
        return self.client.files.upload(file=self.processed_file_path, purpose="batch-api").id

    def delete_provider_file(self):
        self.client.files.delete(id=self.provider_file_id)

    def create_provider_batch(self) -> str:
        return self.client.batches.create_batch(
            file_id=self.provider_file_id,
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
            id=self.batch.output_file_id, output=self.results_file_path
        )
        return read_jsonl_file(self.results_file_path)
