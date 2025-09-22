import typing as t
from functools import cached_property

from pydantic import computed_field

from batchling.experiment import Experiment
from batchling.request import OpenAIBody, OpenAIRequest, ProcessedMessage
from batchling.utils.files import read_jsonl_file

if t.TYPE_CHECKING:
    from openai import OpenAI
    from openai.types.batch import Batch
    from openai.types.file_object import FileObject


class OpenAIExperiment(Experiment):
    @cached_property
    def client(self) -> "OpenAI":
        """Get the client

        Returns:
            OpenAI: The client
        """
        from openai import OpenAI

        return OpenAI(api_key=self.api_key)

    @computed_field
    @cached_property
    def processed_requests(self) -> list[OpenAIRequest]:
        processed_requests: list[OpenAIRequest] = []
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
                OpenAIRequest(
                    custom_id=f"{self.name}-sample-{i}",
                    body=OpenAIBody(
                        messages=messages,
                        max_tokens=raw_request.max_tokens,
                        model=self.model,
                        response_format=self.response_format,
                    ),
                    url=self.endpoint,
                )
            )
        return processed_requests

    def retrieve_provider_file(self):
        return self.client.files.retrieve(self.provider_file_id)

    def retrieve_provider_batch(self):
        return self.client.batches.retrieve(self.batch_id)

    @property
    def provider_file(self) -> t.Union["FileObject", None]:
        if self.provider_file_id is None:
            return None
        return self.retrieve_provider_file()

    @property
    def batch(self) -> t.Union["Batch", None]:
        if self.batch_id is None:
            return None
        return self.retrieve_provider_batch()

    @property
    def status(
        self,
    ) -> t.Literal[
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
            return "created"
        return self.batch.status

    def create_provider_file(self) -> str:
        return self.client.files.create(
            file=open(self.processed_file_path, "rb"), purpose="batch"
        ).id

    def delete_provider_file(self):
        self.client.files.delete(file_id=self.provider_file_id)

    def create_provider_batch(self) -> str:
        return self.client.batches.create(
            input_file_id=self.provider_file_id,
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
        with open(self.results_file_path, "w") as f:
            f.write(self.client.files.content(file_id=self.batch.output_file_id).text)
        return read_jsonl_file(self.results_file_path)
