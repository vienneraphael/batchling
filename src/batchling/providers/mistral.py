import typing as t
from functools import cached_property

from pydantic import computed_field

from batchling.experiment import Experiment
from batchling.request import MistralBody, MistralRequest, ProcessedMessage
from batchling.utils.files import read_jsonl_file

if t.TYPE_CHECKING:
    from mistralai import Mistral
    from mistralai.models import BatchJobOut, RetrieveFileOut


class MistralExperiment(Experiment):
    @cached_property
    def client(self) -> "Mistral":
        """Get the client

        Returns:
            Mistral: The client
        """
        from mistralai import Mistral

        return Mistral(api_key=self.api_key)

    @computed_field
    @cached_property
    def processed_requests(self) -> list[MistralRequest]:
        processed_requests: list[MistralRequest] = []
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
                MistralRequest(
                    custom_id=f"{self.name}-sample-{i}",
                    body=MistralBody(
                        messages=messages,
                        max_tokens=raw_request.max_tokens,
                        response_format=self.response_format,
                    ),
                )
            )
        return processed_requests

    def retrieve_provider_file(self):
        return self.client.files.retrieve(file_id=self.provider_file_id)

    def retrieve_provider_batch(self):
        return self.client.batch.jobs.get(job_id=self.batch_id)

    @property
    def provider_file(self) -> t.Union["RetrieveFileOut", None]:
        if self.provider_file_id is None:
            return None
        return self.retrieve_provider_file()

    @property
    def batch(self) -> t.Union["BatchJobOut", None]:
        if self.batch_id is None:
            return None
        return self.retrieve_provider_batch()

    @property
    def status(
        self,
    ) -> t.Literal[
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
            return "created"
        return self.batch.status

    def create_provider_file(self) -> str:
        return self.client.files.upload(
            file={
                "file_name": self.processed_file_path.split("/")[-1],
                "content": open(self.processed_file_path, "rb"),
            },
            purpose="batch",
        ).id

    def delete_provider_file(self):
        self.client.files.delete(file_id=self.provider_file_id)

    def create_provider_batch(self) -> str:
        return self.client.batch.jobs.create(
            input_files=[self.provider_file_id],
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
        elif self.batch.status == "SUCCESS" and self.batch.output_file:
            self.delete_provider_file()

    def get_provider_results(self) -> list[dict]:
        output = self.client.files.download(file_id=self.batch.output_file)
        with open(self.results_file_path, "w") as f:
            for chunk in output.stream:
                f.write(chunk.decode("utf-8"))
        return read_jsonl_file(self.results_file_path)
