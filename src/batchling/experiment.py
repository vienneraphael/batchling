import json
import os
import typing as t
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from functools import cached_property

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)

from batchling.models import ProviderBatch, ProviderFile
from batchling.request import (
    ProcessedRequest,
    RawRequest,
    raw_request_list_adapter,
)
from batchling.utils.files import write_jsonl_file


class Experiment(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)
    name: str = Field(description="experiment name")
    uid: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="machine-friendly unique identifier",
    )
    title: str | None = Field(
        default=None, description="optional, title briefly summarizing the experiment"
    )
    description: str | None = Field(
        default=None, description="optional, description of the experiment"
    )
    model: str = Field(description="model to use")
    provider: t.Literal["openai", "mistral", "together", "groq", "gemini", "anthropic"] = Field(
        default="openai",
        description="provider to use",
    )
    endpoint: str = Field(
        default="/v1/chat/completions",
        description="generation endpoint to use for the provider, e.g. /v1/chat/completions, /v1/embeddings..",
    )
    api_key: str = Field(
        description="the API key to use for the provider if not using standard naming / env variables",
    )
    raw_requests: list[RawRequest] | None = Field(
        default_factory=list,
        description="optional, the raw requests used to build the batch. Required if processed file path does not exist",
        repr=False,
    )
    response_format: dict | None = Field(
        default_factory=dict, description="optional, the response format to use"
    )
    processed_file_path: str = Field(
        description="the processed batch input file path, sent to the provider. Will be used if path exists, else it will be created by batchling."
    )
    results_file_path: str = Field(
        default="results.jsonl",
        description="the path to the output file where batch results will be saved",
    )
    provider_file_id: str | None = Field(default=None, description="provider batch file id")
    batch_id: str | None = Field(default=None, description="provider batch id")
    created_at: datetime = Field(description="created at")
    updated_at: datetime = Field(description="updated at")

    @field_validator("processed_file_path", mode="before")
    @classmethod
    def check_jsonl_format(cls, value: str):
        if isinstance(value, str):
            if not value.endswith(".jsonl"):
                raise ValueError("processed_file_path must be a .jsonl file")
        return value

    @abstractmethod
    def _headers(self) -> dict[str, str]:
        pass

    def _http_get_json(self, url: str) -> dict:
        """GET request used to retrieve files or batches"""
        response = httpx.get(url, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def _http_post(
        self, url: str, json: dict | None = None, additional_headers: dict | None = None, **kwargs
    ) -> httpx.Response:
        headers = self._headers()
        if additional_headers:
            headers.update(additional_headers)
        response = httpx.post(url, headers=headers, json=json, **kwargs)
        response.raise_for_status()
        return response

    def _http_post_json(
        self, url: str, json: dict | None = None, additional_headers: dict | None = None, **kwargs
    ) -> dict:
        """POST request used to create files or batches"""
        response = self._http_post(url, json=json, additional_headers=additional_headers, **kwargs)
        return response.json()

    def _http_delete(self, url: str) -> None:
        """DELETE request used to delete files or batches"""
        response = httpx.delete(url, headers=self._headers())
        response.raise_for_status()

    def _http_get_text(self, url: str) -> str:
        """GET request used to retrieve batch results or output files"""
        response = httpx.get(url, headers=self._headers())
        response.raise_for_status()
        return response.text

    def _download_results(self, url: str) -> list[dict]:
        """Utility method used to download results from URL and write to file"""
        text_content = self._http_get_text(url)
        results = [json.loads(line) for line in text_content.strip().split("\n")]
        with open(self.results_file_path, "w") as f:
            f.write(text_content)
        return results

    @abstractmethod
    @computed_field(repr=False)
    @cached_property
    def processed_requests(self) -> list[ProcessedRequest]:
        pass

    @abstractmethod
    def retrieve_provider_file(self) -> ProviderFile | str | None:
        pass

    @abstractmethod
    def retrieve_provider_batch(self) -> ProviderBatch | None:
        pass

    @abstractmethod
    def create_provider_file(self) -> str:
        pass

    @abstractmethod
    def delete_provider_file(self):
        pass

    @abstractmethod
    def create_provider_batch(self) -> str:
        pass

    @abstractmethod
    def raise_not_in_running_status(self):
        pass

    @abstractmethod
    def raise_not_in_completed_status(self):
        pass

    @abstractmethod
    def cancel_provider_batch(self):
        pass

    @abstractmethod
    def delete_provider_batch(self):
        pass

    def write_processed_batch_file(self) -> None:
        write_jsonl_file(
            file_path=self.processed_file_path,
            data=[
                processed_request.model_dump_json(exclude_none=True)
                for processed_request in self.processed_requests
            ],
        )

    @abstractmethod
    def get_provider_results(self) -> t.Any:
        pass

    @property
    @abstractmethod
    def provider_file(self) -> ProviderFile | str | None:
        pass

    @property
    @abstractmethod
    def batch(self) -> ProviderBatch | None:
        pass

    @cached_property
    @abstractmethod
    def status(
        self,
    ) -> str:
        pass

    def start(self) -> None:
        """Start the experiment:
        - create the processed file in the provider
        - create the batch in the provider

        Returns:
            None
        """
        if self.status != "created":
            raise ValueError(f"Experiment in status {self.status} cannot be started")
        self.provider_file_id = self.create_provider_file()
        self.batch_id = self.create_provider_batch()

    def cancel(self) -> None:
        """Cancel the experiment:
        - cancel the batch in the provider
        - update the database updated_at in the local db

        Returns:
            None
        """
        self.raise_not_in_running_status()
        self.cancel_provider_batch()

    def get_results(self):
        self.raise_not_in_completed_status()
        dirname = os.path.dirname(self.results_file_path)
        if dirname:
            os.makedirs(name=dirname, exist_ok=True)
        return self.get_provider_results()

    def delete(self):
        """Delete:
        - provider file, if any
        - provider batch, if any
        Returns:
            None
        """
        if os.path.exists(self.processed_file_path):
            os.remove(self.processed_file_path)
        if self.provider_file_id is not None:
            self.delete_provider_file()
        if self.batch_id is not None:
            self.delete_provider_batch()

    def update(self, kwargs: dict) -> "Experiment":
        """Update the experiment

        Parameters
        ----------
        kwargs : dict
            The fields to update

        Returns
        -------
        Experiment
            The updated experiment
        """
        updated_dict_experiment = self.model_dump()
        updated_dict_experiment.update(kwargs)
        # validate model first to avoid updating the database with invalid data
        updated_dict_experiment["raw_requests"] = (
            raw_request_list_adapter.validate_python(updated_dict_experiment["raw_requests"])
            if updated_dict_experiment["raw_requests"]
            else None
        )
        updated_experiment = self.__class__.model_validate(updated_dict_experiment)
        if set(
            [
                "raw_requests",
                "response_format",
                "endpoint",
                "model",
                "processed_file_path",
            ]
        ) & set(kwargs):
            self.write_processed_batch_file()
        if "processed_file_path" in kwargs and os.path.exists(self.processed_file_path):
            os.remove(self.processed_file_path)
        return updated_experiment
