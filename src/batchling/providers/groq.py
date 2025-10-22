import typing as t
from functools import cached_property
import requests
from pydantic import computed_field

from batchling.experiment import Experiment
from batchling.request import GroqBody, GroqRequest, ProcessedMessage
from batchling.utils.files import read_jsonl_file


class GroqExperiment(Experiment):

    BASE_URL: str = "https://api.groq.com/openai/v1"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
        }

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

    def retrieve_provider_file(self) -> dict | None:
        response = requests.get(
            f"{self.BASE_URL}/files/{self.provider_file_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def retrieve_provider_batch(self) -> dict | None:
        response = requests.get(
            f"{self.BASE_URL}/batches/{self.batch_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

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
            response = requests.post(
                f"{self.BASE_URL}/files",
                headers=self._headers(),
                files={"file": (self.processed_file_path.split("/")[-1], f)},
                data={"purpose": "batch"},
            )
            response.raise_for_status()
            return response.json().get("id")

    def delete_provider_file(self) -> None:
        response = requests.delete(
            f"{self.BASE_URL}/files/{self.provider_file_id}",
            headers=self._headers(),
        )
        response.raise_for_status()

    def create_provider_batch(self) -> str:
        response = requests.post(
            f"{self.BASE_URL}/batches",
            headers=self._headers(),
            json={
                "input_file_id": self.provider_file_id,
                "endpoint": self.endpoint,
                "completion_window": "24h",
                "metadata": {"description": self.description},
            }
        )
        response.raise_for_status()
        return response.json().get("id")

    def raise_not_in_running_status(self):
        if self.status not in ["in_progress", "finalizing"]:
            raise ValueError(
                f"Experiment in status {self.status} is not in in_progress or finalizing status"
            )

    def raise_not_in_completed_status(self):
        if self.status != "completed":
            raise ValueError(f"Experiment in status {self.status} is not in completed status")

    def cancel_provider_batch(self) -> None:
        response = requests.post(
            f"{self.BASE_URL}/batches/{self.batch_id}/cancel",
            headers=self._headers(),
        )
        response.raise_for_status()

    def delete_provider_batch(self) -> None:
        if self.batch.get("status") in ["in_progress", "finalizing"]:
            self.cancel_provider_batch()
        elif self.batch.get("status") == "completed" and self.batch.get("output_file_id"):
            self.delete_provider_file()

    def get_provider_results(self) -> list[dict]:
        response = requests.get(
            f"{self.BASE_URL}/files/{self.batch.get('output_file_id')}/content",
            headers=self._headers(),
        )
        response.raise_for_status()
        with open(self.results_file_path, "w") as f:
            f.write(response.text)
        return read_jsonl_file(self.results_file_path)
