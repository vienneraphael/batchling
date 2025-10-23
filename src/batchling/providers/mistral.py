import typing as t
from functools import cached_property
import httpx
from pydantic import computed_field
import base64
from batchling.experiment import Experiment
from batchling.request import MistralBody, MistralRequest, ProcessedMessage
from batchling.utils.files import read_jsonl_file

class MistralExperiment(Experiment):
    BASE_URL: str = "https://api.mistral.ai/v1"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
        }

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

    def retrieve_provider_file(self) -> dict | None:
        response = httpx.get(
            f"{self.BASE_URL}/files/{self.provider_file_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def retrieve_provider_batch(self) -> dict | None:
        response = httpx.get(
            f"{self.BASE_URL}/batch/jobs/{self.batch_id}",
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
        return self.batch.get("status")

    def create_provider_file(self) -> str:
        with open(self.processed_file_path, "rb") as f:
            response = httpx.post(
                f"{self.BASE_URL}/files",
                headers=self._headers(),
                data={"purpose": "batch"},
                files={"file": f},
            )
            response.raise_for_status()
            return response.json().get("id")

    def delete_provider_file(self):
        response = httpx.delete(
            f"{self.BASE_URL}/files/{self.provider_file_id}",
            headers=self._headers(),
        )
        response.raise_for_status()

    def create_provider_batch(self) -> str:
        response = httpx.post(
            f"{self.BASE_URL}/batch/jobs",
            headers=self._headers(),
            json={
                "input_files": [self.provider_file_id],
                "endpoint": self.endpoint,
                "model": self.model,
            }
        )
        response.raise_for_status()
        return response.json().get("id")

    def raise_not_in_running_status(self):
        if self.status not in ["QUEUED", "RUNNING"]:
            raise ValueError(
                f"Experiment in status {self.status} is not in QUEUED or RUNNING status"
            )

    def raise_not_in_completed_status(self):
        if self.status != "SUCCESS":
            raise ValueError(f"Experiment in status {self.status} is not in SUCCESS status")

    def cancel_provider_batch(self) -> None:
        response = httpx.post(
            f"{self.BASE_URL}/batch/jobs/{self.batch_id}/cancel",
            headers=self._headers(),
        )
        response.raise_for_status()

    def delete_provider_batch(self):
        if self.batch.get("status") in ["QUEUED", "RUNNING"]:
            self.cancel_provider_batch()
        elif self.batch.get("status") == "SUCCESS" and self.batch.get("output_file"):
            self.delete_provider_file()

    def get_provider_results(self) -> list[dict]:
        response = httpx.get(
            f"{self.BASE_URL}/files/{self.batch.get('output_file')}/content",
            headers=self._headers(),
        )
        response.raise_for_status()
        with open(self.results_file_path, "w") as f:
            f.write(response.text)
        return read_jsonl_file(self.results_file_path)
