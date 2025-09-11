import os
import typing as t
from abc import ABC, abstractmethod
from datetime import datetime
from functools import cached_property

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from batchling.db.crud import create_experiment, delete_experiment, update_experiment
from batchling.db.session import get_db
from batchling.request import (
    ProcessedRequest,
    RawRequest,
)
from batchling.utils.api import get_default_api_key_from_provider
from batchling.utils.files import write_jsonl_file


class Experiment(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)
    id: str = Field(description="experiment ID")
    name: str = Field(description="name of the experiment")
    description: str | None = Field(default=None, description="description of the experiment")
    model: str = Field(description="model to use")
    provider: t.Literal["openai", "mistral", "together", "groq", "gemini", "anthropic"] = Field(
        default="openai",
        description="provider to use",
    )
    endpoint: str = Field(
        default="/v1/chat/completions",
        description="generation endpoint to use for the provider, e.g. /v1/chat/completions, /v1/embeddings..",
    )
    api_key: str | None = Field(
        default=None,
        description="Optional, the API key to use for the provider if not using standard naming / env variables",
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
    created_at: datetime | None = Field(default=None, description="created at")
    updated_at: datetime | None = Field(default=None, description="updated at")

    def __repr__(self):
        return f"{self.__repr_name__()}(\n    {self.__repr_str__(',\n    ')}\n)"

    @model_validator(mode="after")
    def set_created_at_and_updated_at(self):
        now = datetime.now()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
        return self

    @model_validator(mode="after")
    def set_api_key(self):
        if self.api_key is None:
            self.api_key = get_default_api_key_from_provider(self.provider)
        return self

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

    @property
    @abstractmethod
    def status(
        self,
    ) -> str:
        pass

    @field_validator("created_at", "updated_at")
    def set_datetime(cls, value: datetime | None):
        return value or datetime.now()

    @field_validator("processed_file_path")
    def check_jsonl_format(cls, value: str):
        if isinstance(value, str):
            if not value.endswith(".jsonl"):
                raise ValueError("processed_file_path must be a .jsonl file")
        return value

    def start(self) -> None:
        """Start the experiment:
        - create the processed file in the provider
        - create the batch in the provider
        - update the database updated_at in the local db

        Returns:
            None
        """
        if self.status != "created":
            raise ValueError(f"Experiment in status {self.status} cannot be started")
        self.provider_file_id = self.create_provider_file()
        self.batch_id = self.create_provider_batch()
        with get_db() as db:
            update_experiment(
                db=db,
                id=self.id,
                updated_at=datetime.now(),
                batch_id=self.batch_id,
                provider_file_id=self.provider_file_id,
            )

    def cancel(self) -> None:
        """Cancel the experiment:
        - cancel the batch in the provider
        - update the database updated_at in the local db

        Returns:
            None
        """
        self.raise_not_in_running_status()
        self.cancel_provider_batch()
        with get_db() as db:
            update_experiment(db=db, id=self.id, updated_at=datetime.now())

    def get_results(self):
        os.makedirs(os.path.dirname(self.results_file_path), exist_ok=True)
        self.raise_not_in_completed_status()
        return self.get_provider_results()

    def save(self):
        if self.status != "created":
            raise ValueError(f"Can only save an experiment in created status. Found: {self.status}")
        with get_db() as db:
            create_experiment(
                db=db,
                id=self.id,
                model=self.model,
                api_key=self.api_key,
                name=self.name,
                description=self.description,
                provider=self.provider,
                endpoint=self.endpoint,
                raw_requests=self.raw_requests,
                response_format=self.response_format,
                processed_file_path=self.processed_file_path,
                results_file_path=self.results_file_path,
                created_at=self.created_at,
                updated_at=self.updated_at,
            )

    def delete_local_experiment(self):
        with get_db() as db:
            delete_experiment(db=db, id=self.id)
        if os.path.exists(self.processed_file_path):
            os.remove(self.processed_file_path)

    def delete(self):
        """Delete:
        - experiment from the database, if any
        - local file, if any
        - provider file, if any
        - provider batch, if any
        - provider output file, if any

        Returns:
            None
        """
        self.delete_local_experiment()
        if self.provider_file_id is not None:
            self.delete_provider_file()
        if self.batch_id is not None:
            self.delete_provider_batch()

    def update(self, **kwargs) -> "Experiment":
        """Update the experiment by updating the database

        Returns:
            Experiment: The updated experiment
        """
        if self.status != "created":
            raise ValueError(
                f"Can only update an experiment in created status. Found: {self.status}"
            )
        if "id" in kwargs:
            raise ValueError(
                "id cannot be updated, please delete the experiment and create a new one"
            )
        kwargs["updated_at"] = datetime.now()
        exp_dict = self.model_dump()
        exp_dict.update(kwargs)
        # validate model first to avoid updating the database with invalid data
        exp_dict["raw_requests"] = [
            RawRequest.model_validate(raw_request) for raw_request in exp_dict["raw_requests"]
        ]
        updated_experiment = self.__class__.model_validate(exp_dict)
        with get_db() as db:
            db_experiment = update_experiment(db=db, id=self.id, **kwargs)
        if db_experiment is None:
            raise ValueError(f"Experiment with id: {self.id} not found")
        return updated_experiment
