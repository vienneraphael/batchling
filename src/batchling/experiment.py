import json
import os
import typing as t
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from functools import cached_property

import httpx
import structlog
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from batchling.models import BatchResult, ProviderBatch, ProviderFile
from batchling.request import (
    ProcessedRequest,
    RawRequest,
    raw_request_list_adapter,
)
from batchling.utils.files import write_jsonl_file

log = structlog.get_logger(__name__)


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
    raw_requests: list[RawRequest] = Field(
        default_factory=list,
        description="optional, the raw requests used to build the batch. Required if processed file path does not exist",
        repr=False,
    )
    response_format: dict | None = Field(
        default_factory=dict, description="optional, the response format to use"
    )
    thinking_level: str | None = Field(
        default=None, description="optional, thinking level (for OpenAI and Gemini 3.0+)"
    )
    thinking_budget: int | None = Field(
        default=None,
        description="optional, thinking budget in tokens (for Anthropic and Gemini 2.5 series)",
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

    @field_validator("raw_requests", mode="before")
    @classmethod
    def validate_raw_requests(cls, value: list[dict] | None) -> list[RawRequest] | None:
        if value is None:
            return None
        return raw_request_list_adapter.validate_python(value)

    @model_validator(mode="after")
    def validate_thinking_params(self) -> "Experiment":
        """Validate that both thinking_level and thinking_budget are not set."""
        if self.thinking_level is not None and self.thinking_budget is not None:
            raise ValueError(
                "Cannot set both thinking_level and thinking_budget. Use only one based on your provider's requirements."
            )
        return self

    @abstractmethod
    def _headers(self) -> dict[str, str]:
        pass

    def _http_get_json(self, url: str) -> dict:
        """GET request used to retrieve files or batches"""
        response = httpx.get(url, headers=self._headers(), timeout=30.0)
        response.raise_for_status()
        return response.json()

    def _http_post(
        self, url: str, json: dict | None = None, additional_headers: dict | None = None, **kwargs
    ) -> httpx.Response:
        headers = self._headers()
        if additional_headers:
            headers.update(additional_headers)
        response = httpx.post(url, headers=headers, json=json, timeout=30.0, **kwargs)
        if response.is_error:
            try:
                error_body = response.json()
            except Exception:
                error_body = response.text
            log.error(
                "HTTP POST request failed",
                url=url,
                status_code=response.status_code,
                error_body=error_body,
            )
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
        response = httpx.delete(url, headers=self._headers(), timeout=10.0)
        response.raise_for_status()

    def _http_get_text(self, url: str) -> str:
        """GET request used to retrieve batch results or output files"""
        response = httpx.get(url, headers=self._headers(), timeout=30.0)
        response.raise_for_status()
        return response.text

    def _download_results(self, url: str) -> list[BatchResult]:
        log.debug("Downloading results from URL", url=url)
        text_content = self._http_get_text(url)
        raw_results = [
            json.loads(line) for line in text_content.strip().split("\n") if line.strip()
        ]
        unified_results: list[BatchResult] = [
            BatchResult.from_provider_response(self.provider, raw) for raw in raw_results
        ]
        with open(self.results_file_path, "w") as f:
            for result in unified_results:
                f.write(result.model_dump_json() + "\n")
        return unified_results

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

    def get_results(self) -> list[BatchResult]:
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
                "thinking_level",
                "thinking_budget",
            ]
        ) & set(kwargs):
            self.write_processed_batch_file()
        if "processed_file_path" in kwargs and os.path.exists(self.processed_file_path):
            os.remove(self.processed_file_path)
        return updated_experiment
