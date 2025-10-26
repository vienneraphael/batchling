import typing as t
from functools import cached_property

from pydantic import computed_field

from batchling.experiment import Experiment
from batchling.models import ProviderBatch, ProviderFile
from batchling.request import (
    GeminiBody,
    GeminiConfig,
    GeminiMessage,
    GeminiPart,
    GeminiRequest,
    GeminiSystemInstruction,
    RawMessage,
)


class GeminiExperiment(Experiment):
    BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    UPLOAD_BASE_URL: str = "https://generativelanguage.googleapis.com/upload/v1beta"
    DOWNLOAD_BASE_URL: str = "https://generativelanguage.googleapis.com/download/v1beta"

    def _headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": self.api_key,
        }

    @computed_field
    @cached_property
    def processed_requests(self) -> list[GeminiRequest]:
        processed_requests: list[GeminiRequest] = []
        for i, raw_request in enumerate(self.raw_requests):
            messages = [
                RawMessage(role=message.role, content=message.content)
                for message in raw_request.messages
            ]
            processed_requests.append(
                GeminiRequest(
                    key=f"{self.name}-sample-{i}",
                    request=GeminiBody(
                        system_instruction=GeminiSystemInstruction(
                            parts=[GeminiPart(text=raw_request.system_prompt)]
                        )
                        if raw_request.system_prompt
                        else None,
                        contents=[
                            GeminiMessage(
                                role=message.role,
                                parts=[GeminiPart(text=message.content)],
                            )
                            for message in messages
                        ],
                        generation_config=GeminiConfig(
                            response_mime_type="application/json",
                            response_json_schema=self.response_format["json_schema"]["schema"],
                        )
                        if self.response_format
                        else None,
                    ),
                )
            )
        return processed_requests

    def retrieve_provider_file(self) -> ProviderFile | None:
        data = self._http_get_json(f"{self.BASE_URL}/{self.provider_file_id}")
        return ProviderFile.model_validate(data)

    def retrieve_provider_batch(self) -> ProviderBatch | None:
        data = self._http_get_json(f"{self.BASE_URL}/{self.batch_id}")
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
    ) -> t.Literal[
        "created",
        "BATCH_STATE_UNSPECIFIED",
        "BATCH_STATE_PENDING",
        "BATCH_STATE_RUNNING",
        "BATCH_STATE_SUCCEEDED",
        "BATCH_STATE_FAILED",
        "BATCH_STATE_CANCELLED",
        "BATCH_STATE_EXPIRED",
    ]:
        if self.batch_id is None:
            return "created"
        return self.batch.status

    def prepare_provider_file(self) -> str:
        """Prepare the provider file by uploading it to the provider and returning the upload URL.

        Returns:
            str: The upload URL of the provider file.
        """
        additional_headers = {
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
        }
        data = {
            "file": {
                "display_name": self.processed_file_path.split("/")[-1],
            }
        }
        response = self._http_post(
            url=f"{self.UPLOAD_BASE_URL}/files", additional_headers=additional_headers, json=data
        )
        return response.headers.get("X-Goog-Upload-URL")

    def upload_provider_file(self, upload_url: str) -> str:
        """Upload the provider file to the provider and return the file name.

        Args:
            upload_url (str): The upload URL of the provider file.

        Returns:
            str: The file name of the provider file.
        """
        additional_headers = {
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        }
        with open(self.processed_file_path, "rb") as f:
            upload_response = self._http_post_json(
                url=upload_url,
                additional_headers=additional_headers,
                content=f.read(),
            )
        return ProviderFile.model_validate(upload_response).id

    def create_provider_file(self) -> str:
        upload_url = self.prepare_provider_file()
        file_name = self.upload_provider_file(upload_url=upload_url)
        return ProviderFile.model_validate({"name": file_name}).id

    def delete_provider_file(self):
        self._http_delete(f"{self.BASE_URL}/{self.provider_file_id}")

    def create_provider_batch(self) -> str:
        data = {
            "batch": {
                "display_name": self.name,
                "input_config": {
                    "file_name": self.provider_file_id,
                },
            }
        }
        response = self._http_post_json(
            f"{self.BASE_URL}/models/{self.model}:batchGenerateContent",
            json=data,
        )
        return ProviderBatch.model_validate(response).id

    def raise_not_in_running_status(self):
        if self.status not in ["BATCH_STATE_RUNNING", "BATCH_STATE_PENDING"]:
            raise ValueError(
                f"Experiment in status {self.status} is not in BATCH_STATE_RUNNING or BATCH_STATE_PENDING status"
            )

    def raise_not_in_completed_status(self):
        if self.status != "BATCH_STATE_SUCCEEDED":
            raise ValueError(
                f"Experiment in status {self.status} is not in BATCH_STATE_SUCCEEDED status"
            )

    def cancel_provider_batch(self):
        self._http_post_json(f"{self.BASE_URL}/{self.batch_id}:cancel")

    def delete_provider_batch(self):
        status = self.status
        if status in ["BATCH_STATE_RUNNING", "BATCH_STATE_PENDING"]:
            self.cancel_provider_batch()
        elif status == "BATCH_STATE_SUCCEEDED":
            batch = self.batch
            if batch and batch.output_file_id:
                self.delete_provider_file()

    def get_provider_results(self) -> list[dict]:
        batch = self.batch
        if not batch or not batch.output_file_id:
            return []
        return self._download_results(
            f"{self.DOWNLOAD_BASE_URL}/{batch.output_file_id}:download?alt=media"
        )
