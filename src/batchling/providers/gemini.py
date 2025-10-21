import typing as t
from functools import cached_property

import requests
from pydantic import computed_field

from batchling.experiment import Experiment
from batchling.request import (
    GeminiBody,
    GeminiConfig,
    GeminiMessage,
    GeminiPart,
    GeminiRequest,
    GeminiSystemInstruction,
    RawMessage,
)
from batchling.utils.files import read_jsonl_file

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

    def retrieve_provider_file(self):
        response = requests.get(
            f"{self.BASE_URL}/{self.provider_file_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def retrieve_provider_batch(self):
        response = requests.get(
            f"{self.BASE_URL}/{self.batch_id}",
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
        batch = self.batch
        if batch is None:
            return "created"
        return batch.get("metadata").get("state")


    def prepare_provider_file(self) -> str:
        """Prepare the provider file by uploading it to the provider and returning the upload URL.

        Returns:
            str: The upload URL of the provider file.
        """
        headers = {
            "x-goog-api-key": self.api_key,
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Type": "application/jsonl",
            "Content-Type": "application/jsonl",
        }
        data = {
            "file": {
                "display_name": self.processed_file_path.split("/")[-1],
            }
        }
        response = requests.post(
            f"{self.UPLOAD_BASE_URL}/files",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return response.headers.get("X-Goog-Upload-URL")

    def upload_provider_file(self, upload_url: str) -> str:
        """Upload the provider file to the provider and return the file name.

        Args:
            upload_url (str): The upload URL of the provider file.

        Returns:
            str: The file name of the provider file.
        """
        upload_headers = {
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize"
        }
        with open(self.processed_file_path, "rb") as f:
            upload_response = requests.post(
                upload_url,
                headers=upload_headers,
                data=f
            )
        upload_response.raise_for_status()
        return upload_response.json().get("file").get("name")


    def create_provider_file(self) -> str:
        upload_url = self.prepare_provider_file()
        return self.upload_provider_file(upload_url=upload_url)

    def delete_provider_file(self):
        response = requests.delete(
            f"{self.BASE_URL}/{self.provider_file_id}",
            headers=self._headers(),
        )
        response.raise_for_status()

    def create_provider_batch(self) -> str:
        data = {
            "batch": {
                "display_name": self.name,
                "input_config": {
                    "file_name": self.provider_file_id,
                }
            }
        }
        response = requests.post(
            f"{self.BASE_URL}/models/{self.model}:batchGenerateContent",
            headers=self._headers(),
            json=data,
        )
        response.raise_for_status()
        return response.json().get("name")

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
        response = requests.post(
            f"{self.BASE_URL}/{self.batch_id}:cancel",
            headers=self._headers(),
        )
        response.raise_for_status()

    def delete_provider_batch(self):
        if self.status in ["BATCH_STATE_RUNNING", "BATCH_STATE_PENDING"]:
            self.cancel_provider_batch()
        elif self.status == "BATCH_STATE_SUCCEEDED":
            batch = self.batch or {}
            if (
                batch.get("output_file_id")
                or (isinstance(batch.get("dest"), dict) and batch["dest"].get("file_name"))
            ):
                self.delete_provider_file()

    def get_provider_results(self) -> list[dict]:
        batch = self.batch
        responses_file = batch.get("response").get("responsesFile")
        response = requests.get(
            f"{self.DOWNLOAD_BASE_URL}/{responses_file}:download?alt=media",
            headers=self._headers(),
        )
        response.raise_for_status()
        text_content = response.text

        with open(self.results_file_path, "w") as f:
            f.write(text_content)
        return read_jsonl_file(file_path=self.results_file_path)
