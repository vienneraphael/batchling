import os
import typing as t
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from functools import cached_property

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)

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
        default_factory=lambda: str(uuid.uuid4()), description="machine-friendly unique identifier"
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

    def __repr__(self):
        return f"{self.__repr_name__()}(\n    {self.__repr_str__(',\n    ')}\n)"

    @field_validator("processed_file_path")
    def check_jsonl_format(cls, value: str):
        if isinstance(value, str):
            if not value.endswith(".jsonl"):
                raise ValueError("processed_file_path must be a .jsonl file")
        return value

    @abstractmethod
    @cached_property
    def client(
        self,
    ) -> t.Any:
        pass

    @abstractmethod
    @computed_field(repr=False)
    @cached_property
    def processed_requests(self) -> list[ProcessedRequest]:
        pass

    @abstractmethod
    def retrieve_provider_file(self):
        pass

    @abstractmethod
    def retrieve_provider_batch(self):
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
    def provider_file(self) -> t.Any:
        pass

    @property
    @abstractmethod
    def batch(self) -> t.Any:
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
        os.makedirs(os.path.dirname(self.results_file_path), exist_ok=True)
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

    def update(self, **kwargs) -> "Experiment":
        """Update the experiment

        Returns:
            Experiment: The updated experiment
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
            ["raw_requests", "response_format", "endpoint", "model", "processed_file_path"]
        ) & set(kwargs):
            self.write_processed_batch_file()
        if "processed_file_path" in kwargs and os.path.exists(self.processed_file_path):
            os.remove(self.processed_file_path)
        return updated_experiment
