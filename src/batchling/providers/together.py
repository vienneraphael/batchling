from functools import cached_property

import structlog
from pydantic import computed_field

from batchling.experiment import Experiment
from batchling.models import BatchResult, ProviderBatch, ProviderFile
from batchling.request import ProcessedMessage, TogetherBody, TogetherRequest

log = structlog.get_logger(__name__)


class TogetherExperiment(Experiment):
    BASE_URL: str = "https://api.together.xyz/v1"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
        }

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

    def retrieve_provider_file(self) -> ProviderFile | None:
        data = self._http_get_json(f"{self.BASE_URL}/files/{self.provider_file_id}")
        return ProviderFile.model_validate(data)

    def retrieve_provider_batch(self) -> ProviderBatch | None:
        data = self._http_get_json(f"{self.BASE_URL}/batches/{self.batch_id}")
        return ProviderBatch.model_validate(data)

    @property
    def provider_file(self) -> ProviderFile | None:
        if self.provider_file_id is None:
            return None
        return self.retrieve_provider_file()

    @property
    def batch(self) -> ProviderBatch | None:
        if self.batch_id is None:
            return None
        return self.retrieve_provider_batch()

    @property
    def status(
        self,
    ) -> str:
        if self.batch is None:
            return "created"
        return self.batch.status

    def create_provider_file(self) -> str:
        with open(self.processed_file_path, "rb") as f:
            response = self._http_post_json(
                f"{self.BASE_URL}/files/upload",
                data={"file_name": self.processed_file_path.split("/")[-1], "purpose": "batch-api"},
                files={"file": f},
            )
        return ProviderFile.model_validate(response).id

    def delete_provider_file(self):
        self._http_delete(f"{self.BASE_URL}/files/{self.provider_file_id}")

    def create_provider_batch(self) -> str:
        response = self._http_post_json(
            f"{self.BASE_URL}/batches",
            json={
                "input_file_id": self.provider_file_id,
                "endpoint": self.endpoint,
            },
        )
        return ProviderBatch.model_validate(response).id

    def raise_not_in_running_status(self):
        if self.status not in ["IN_PROGRESS", "VALIDATING"]:
            raise ValueError(
                f"Experiment in status {self.status} is not in IN_PROGRESS or VALIDATING status"
            )

    def raise_not_in_completed_status(self):
        if self.status != "COMPLETED":
            raise ValueError(f"Experiment in status {self.status} is not in COMPLETED status")

    def cancel_provider_batch(self):
        self._http_post_json(f"{self.BASE_URL}/batches/{self.batch_id}/cancel")

    def delete_provider_batch(self):
        batch = self.batch
        if batch is None:
            return
        if batch.status in ["IN_PROGRESS", "VALIDATING"]:
            self.cancel_provider_batch()
        elif batch.status == "COMPLETED" and batch.output_file_id:
            self.delete_provider_file()

    def get_provider_results(self) -> list[BatchResult]:
        batch = self.batch
        log.debug("Getting provider results", batch=batch)
        if batch is None:
            return []
        if not batch.output_file_id:
            return self._download_results(f"{self.BASE_URL}/files/{batch.error_file_id}/content")
        return self._download_results(f"{self.BASE_URL}/files/{batch.output_file_id}/content")
