import typing as t
from functools import cached_property

from pydantic import computed_field

from batchling.experiment import Experiment
from batchling.request import OpenAIBody, OpenAIRequest, ProcessedMessage

class OpenAIExperiment(Experiment):
    BASE_URL: str = "https://api.openai.com/v1"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
        }

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
                    headers=self._headers(),
                )
            )
        return processed_requests

    def retrieve_provider_file(self) -> dict | None:
        return self._http_get_json(f"{self.BASE_URL}/files/{self.provider_file_id}")

    def retrieve_provider_batch(self) -> dict | None:
        return self._http_get_json(f"{self.BASE_URL}/batches/{self.batch_id}")

    @property
    def provider_file(self) -> dict | None:
        if self.provider_file_id is None:
            return None
        return self.retrieve_provider_file()

    @property
    def batch(self) -> dict | None:
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
        return self.batch.get("status")

    def create_provider_file(self) -> str:
        with open(self.processed_file_path, "rb") as f:
            response = self._http_post_json(
                f"{self.BASE_URL}/files",
                files={"file": (self.processed_file_path.split("/")[-1], f, "application/jsonl")},
                data={"purpose": "batch"},
            )
            return response.get("id")

    def delete_provider_file(self) -> None:
        self._http_delete(f"{self.BASE_URL}/files/{self.provider_file_id}")

    def create_provider_batch(self) -> str:
        response = self._http_post_json(
            f"{self.BASE_URL}/batches",
            json={
                "input_file_id": self.provider_file_id,
                "endpoint": self.endpoint,
                "completion_window": "24h",
                "metadata": {"description": self.description},
            }
        )
        return response.get("id")

    def raise_not_in_running_status(self):
        if self.status != "running":
            raise ValueError(f"Experiment in status {self.status} is not in running status")

    def raise_not_in_completed_status(self):
        if self.status != "completed":
            raise ValueError(f"Experiment in status {self.status} is not in completed status")

    def cancel_provider_batch(self) -> None:
        self._http_post_json(f"{self.BASE_URL}/batches/{self.batch_id}/cancel")

    def delete_provider_batch(self) -> None:
        if self.batch.get("status") == "in_progress":
            self.cancel_provider_batch()
        elif self.batch.get("status") == "completed" and self.batch.get("output_file_id"):
            self.delete_provider_file()

    def get_provider_results(self) -> list[dict]:
        return self._download_results(
            f"{self.BASE_URL}/files/{self.batch.get('output_file_id')}/content"
        )
