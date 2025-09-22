import typing as t
from functools import cached_property

from pydantic import computed_field

from batchling.experiment import Experiment
from batchling.request import GroqBody, GroqRequest, ProcessedMessage
from batchling.utils.files import read_jsonl_file

if t.TYPE_CHECKING:
    from groq import Groq
    from groq.resources.batches import BatchRetrieveResponse
    from groq.resources.files import FileInfoResponse


class GroqExperiment(Experiment):
    @cached_property
    def client(self) -> "Groq":
        """Get the client

        Returns:
            Groq: The client
        """
        from groq import Groq

        return Groq(api_key=self.api_key)

    @computed_field
    @cached_property
    def processed_requests(self) -> list[GroqRequest]:
        processed_requests: list[GroqRequest] = []
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
                GroqRequest(
                    custom_id=f"{self.name}-sample-{i}",
                    body=GroqBody(
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
        return self.client.files.info(file_id=self.provider_file_id)

    def retrieve_provider_batch(self):
        return self.client.batches.retrieve(batch_id=self.batch_id)

    @property
    def provider_file(self) -> t.Union["FileInfoResponse", None]:
        if self.provider_file_id is None:
            return None
        return self.retrieve_provider_file()

    @property
    def batch(self) -> t.Union["BatchRetrieveResponse", None]:
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
            completion_window="24h",
            endpoint=self.endpoint,
            input_file_id=self.provider_file_id,
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
        output.write_to_file(self.results_file_path)
        return read_jsonl_file(self.results_file_path)
