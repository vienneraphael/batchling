import typing as t
from functools import cached_property

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
from batchling.utils.files import read_jsonl_file, write_jsonl_file

if t.TYPE_CHECKING:
    from google.genai import Client
    from google.genai.types import BatchJob, File


class GeminiExperiment(Experiment):
    @cached_property
    def client(self) -> "Client":
        """Get the client

        Returns:
            Client: The client
        """
        from google.genai import Client

        return Client(api_key=self.api_key)

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
                                role=message.role, parts=[GeminiPart(text=message.content)]
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
        return self.client.files.get(name=self.provider_file_id)

    def retrieve_provider_batch(self):
        return self.client.batches.get(name=self.batch_id)

    @property
    def provider_file(self) -> t.Union["File", None]:
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
        "JOB_STATE_UNSPECIFIED",
        "JOB_STATE_QUEUED",
        "JOB_STATE_PENDING",
        "JOB_STATE_RUNNING",
        "JOB_STATE_SUCCEEDED",
        "JOB_STATE_FAILED",
        "JOB_STATE_CANCELLING",
        "JOB_STATE_CANCELLED",
        "JOB_STATE_PAUSED",
        "JOB_STATE_EXPIRED",
        "JOB_STATE_UPDATING",
        "JOB_STATE_PARTIALLY_SUCCEEDED",
    ]:
        if self.batch_id is None:
            return "created"
        return self.batch.state.name

    def create_provider_file(self) -> str:
        from google.genai.types import UploadFileConfig

        return self.client.files.upload(
            file=self.processed_file_path,
            config=UploadFileConfig(
                display_name=self.processed_file_path.split("/")[-1], mime_type="jsonl"
            ),
        ).name

    def delete_provider_file(self):
        self.client.files.delete(name=self.provider_file_id)

    def create_provider_batch(self) -> str:
        return self.client.batches.create(
            model=self.model,
            src=self.provider_file_id,
            config={"display_name": self.processed_file_path.split("/")[-1]},
        ).name

    def raise_not_in_running_status(self):
        if self.status not in ["JOB_STATE_RUNNING", "JOB_STATE_PENDING"]:
            raise ValueError(
                f"Experiment in status {self.status} is not in JOB_STATE_RUNNING or JOB_STATE_PENDING status"
            )

    def raise_not_in_completed_status(self):
        if self.status != "JOB_STATE_SUCCEEDED":
            raise ValueError(
                f"Experiment in status {self.status} is not in JOB_STATE_SUCCEEDED status"
            )

    def cancel_provider_batch(self):
        self.client.batches.cancel(name=self.batch_id)

    def delete_provider_batch(self):
        if self.status in ["JOB_STATE_RUNNING", "JOB_STATE_PENDING"]:
            self.cancel_provider_batch()
        elif self.status == "JOB_STATE_SUCCEEDED" and self.batch.output_file_id:
            self.delete_provider_file()

    def get_provider_results(self) -> list[dict]:
        output = (
            self.client.files.download(file=self.batch.dest.file_name)
            .decode("utf-8")
            .strip("\n")
            .split("\n")
        )
        write_jsonl_file(file_path=self.results_file_path, data=output)
        return read_jsonl_file(file_path=self.results_file_path)
