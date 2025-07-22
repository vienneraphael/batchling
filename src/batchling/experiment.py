import os
import typing as t
from abc import ABC, abstractmethod
from datetime import datetime
from functools import cached_property

from httpx import Response
from mistralai import Mistral
from mistralai.models import BatchJobOut, RetrieveFileOut
from openai import OpenAI
from openai._legacy_response import HttpxBinaryResponseContent
from openai.types.batch import Batch
from openai.types.file_object import FileObject
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)

from batchling.batch_utils import write_input_batch_file
from batchling.db.crud import create_experiment, delete_experiment, update_experiment
from batchling.db.session import get_db, init_db


class Experiment(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)
    id: str = Field(description="experiment ID")
    name: str = Field(description="name of the experiment")
    description: str | None = Field(default=None, description="description of the experiment")
    model: str = Field(description="model to use")
    provider: t.Literal["mistral"] | None = Field(
        default=None,
        description="provider to use if not compatible with OAI Batch API",
    )
    base_url: str | None = Field(
        default=None,
        description="base url of the used provider. Must be compatible with OAI Batch API. Defaults to OAI base url",
    )
    endpoint: str | None = Field(
        default="v1/chat/completions",
        description="endpoint to use for the provider",
    )
    api_key_name: str = Field(
        default="OPENAI_API_KEY",
        description="API key name for the used provider, uses OAI key from env variables by default",
    )
    template_messages: list[dict] | None = Field(
        default=None, description="messages template to use", repr=False
    )
    placeholders: list[dict] | None = Field(
        default=None, description="placeholders to map in the template messages", repr=False
    )
    response_format: dict | None = Field(default=None, description="response model to use")
    input_file_path: str | None = Field(default=None, description="input file path")
    is_setup: bool = Field(default=False, description="whether the experiment is setup")
    input_file_id: str | None = Field(default=None, description="input file id")
    batch_id: str | None = Field(default=None, description="batch id")
    created_at: datetime | None = Field(default=None, description="created at")
    updated_at: datetime | None = Field(default=None, description="updated at")

    def __repr__(self):
        return f"{self.__repr_name__()}(\n    {self.__repr_str__(',\n    ')}\n)"

    def model_post_init(self, context):
        init_db()

    @abstractmethod
    @computed_field(repr=False)
    @cached_property
    def client(self) -> OpenAI | Mistral:
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

    def write_jsonl_input_file(self) -> None:
        write_input_batch_file(
            file_path=self.input_file_path,
            custom_id=self.id,
            model=self.model,
            messages=self.template_messages,
            response_format=self.response_format,
            placeholders=self.placeholders,
            provider=self.provider,
        )

    @abstractmethod
    def get_provider_results(self):
        pass

    @abstractmethod
    @computed_field(repr=False)
    @property
    def input_file(self) -> FileObject | RetrieveFileOut | None:
        pass

    @abstractmethod
    @computed_field(repr=False)
    @property
    def batch(self) -> Batch | BatchJobOut | None:
        pass

    @abstractmethod
    @computed_field
    @property
    def status(
        self,
    ) -> str:
        pass

    @field_validator("created_at", "updated_at")
    def set_datetime(cls, value: datetime | None):
        return value or datetime.now()

    @field_validator("input_file_path")
    def check_jsonl_format(cls, value: str):
        if isinstance(value, str):
            if not value.endswith(".jsonl"):
                raise ValueError("input_file_path must be a .jsonl file")
        return value

    def setup(self) -> None:
        """Setup the experiment locally:
        - write the local input file if it does not exist already
        - update the experiment status to setup
        - update the database status and updated_at in the local db

        Returns:
            None
        """
        if self.status != "created":
            raise ValueError(f"Experiment in status {self.status} is not in created status")
        if not os.path.exists(self.input_file_path):
            self.write_jsonl_input_file()
        self.is_setup = True
        with get_db() as db:
            update_experiment(db=db, id=self.id, is_setup=self.is_setup, updated_at=datetime.now())

    def start(self) -> None:
        """Start the experiment:
        - create the input file in the provider
        - create the batch in the provider
        - update the database updated_at in the local db

        Returns:
            None
        """
        if self.status != "setup":
            raise ValueError(f"Experiment in status {self.status} is not in setup status")
        self.input_file_id = self.create_provider_file()
        self.batch_id = self.create_provider_batch()
        with get_db() as db:
            update_experiment(
                db=db,
                id=self.id,
                updated_at=datetime.now(),
                batch_id=self.batch_id,
                input_file_id=self.input_file_id,
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

    def get_results(self) -> HttpxBinaryResponseContent:
        """Get the results of the experiment

        Returns:
            HttpxBinaryResponseContent: The results
        """
        self.raise_not_in_completed_status()
        return self.get_provider_results()

    def save(self):
        if self.status != "created":
            raise ValueError(
                f"Can only create an experiment in created status. Found: {self.status}"
            )
        with get_db() as db:
            create_experiment(
                db=db,
                id=self.id,
                model=self.model,
                **self.model_dump(
                    exclude={
                        "id",
                        "model",
                        "created_at",
                        "updated_at",
                        "input_file",
                        "batch",
                        "client",
                        "status",
                    }
                ),
            )

    def delete_local_experiment(self):
        with get_db() as db:
            delete_experiment(db=db, id=self.id)
        if os.path.exists(self.input_file_path):
            os.remove(self.input_file_path)

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
        if self.input_file_id is not None:
            self.delete_provider_file(file_id=self.input_file_id)
        if self.batch_id is not None:
            self.delete_provider_batch()

    def update(self, **kwargs) -> "Experiment":
        """Update the experiment by updating the database

        Returns:
            Experiment: The updated experiment
        """
        if self.is_setup:
            raise ValueError(
                f"Can only update an experiment in created status. Found: {self.status}"
            )
        if "id" in kwargs:
            raise ValueError(
                "id cannot be updated, please delete the experiment and create a new one"
            )
        exp_dict = self.model_dump()
        exp_dict.update(kwargs)
        # validate model first to avoid updating the database with invalid data
        self.model_validate(exp_dict)
        with get_db() as db:
            db_experiment = update_experiment(db=db, id=self.id, **kwargs)
        if db_experiment is None:
            raise ValueError(f"Experiment with id: {self.id} not found")
        return self.model_validate(db_experiment)


class OpenAIExperiment(Experiment):
    @computed_field(repr=False)
    @cached_property
    def client(self) -> OpenAI:
        """Get the client

        Returns:
            OpenAI: The client
        """
        return OpenAI(api_key=os.getenv(self.api_key_name), base_url=self.base_url)

    def retrieve_provider_file(self):
        return self.client.files.retrieve(self.input_file_id)

    def retrieve_provider_batch(self):
        return self.client.batches.retrieve(self.batch_id)

    @computed_field
    @property
    def input_file(self) -> FileObject | None:
        if self.input_file_id is None:
            return None
        return self.retrieve_provider_file()

    @computed_field
    @property
    def batch(self) -> Batch | None:
        if self.batch_id is None:
            return None
        return self.retrieve_provider_batch()

    @computed_field
    @property
    def status(
        self,
    ) -> t.Literal[
        "setup",
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
            if self.is_setup:
                return "setup"
            return "created"
        return self.batch.status

    def create_provider_file(self) -> str:
        return self.client.files.create(file=open(self.input_file_path, "rb"), purpose="batch").id

    def delete_provider_file(self, file_id: str):
        self.client.files.delete(file_id=file_id)

    def create_provider_batch(self) -> str:
        return self.client.batches.create(
            input_file_id=self.input_file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"description": self.description},
        ).id

    def raise_not_in_running_status(self):
        if self.status != "running":
            raise ValueError(f"Experiment in status {self.status} is not in running status")

    def raise_not_in_completed_status(self):
        if self.status != "completed":
            raise ValueError(f"Experiment in status {self.status} is not in completed status")

    def cancel_provider_batch(self):
        self.client.batches.cancel(self.batch_id)

    def delete_provider_batch(self):
        if self.batch.status == "in_progress":
            self.cancel_provider_batch()
        elif self.batch.status == "completed" and self.batch.output_file_id:
            self.delete_provider_file(file_id=self.batch.output_file_id)

    def get_provider_results(self) -> HttpxBinaryResponseContent:
        return self.client.files.content(self.batch.output_file_id)


class MistralExperiment(Experiment):
    @computed_field(repr=False)
    @cached_property
    def client(self) -> Mistral:
        """Get the client

        Returns:
            Mistral: The client
        """
        return Mistral(api_key=os.getenv(self.api_key_name))

    def retrieve_provider_file(self):
        return self.client.files.retrieve(file_id=self.input_file_id)

    def retrieve_provider_batch(self):
        return self.client.batch.jobs.get(job_id=self.batch_id)

    @computed_field
    @property
    def input_file(self) -> RetrieveFileOut | None:
        if self.input_file_id is None:
            return None
        return self.retrieve_provider_file()

    @computed_field
    @property
    def batch(self) -> BatchJobOut | None:
        if self.batch_id is None:
            return None
        return self.retrieve_provider_batch()

    @computed_field
    @property
    def status(
        self,
    ) -> t.Literal[
        "setup",
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
            if self.is_setup:
                return "setup"
            return "created"
        return self.batch.status

    def create_provider_file(self) -> str:
        return self.client.files.upload(
            file={
                "file_name": self.input_file_path.split("/")[-1],
                "content": open(self.input_file_path, "rb"),
            },
            purpose="batch",
        ).id

    def delete_provider_file(self, file_id: str):
        self.client.files.delete(file_id=file_id)

    def create_provider_batch(self) -> str:
        return self.client.batch.jobs.create(
            input_files=[self.input_file_id],
            endpoint=self.endpoint,
            model=self.model,
            metadata={"description": self.description},
        ).id

    def raise_not_in_running_status(self):
        if self.status not in ["QUEUED", "RUNNING"]:
            raise ValueError(
                f"Experiment in status {self.status} is not in QUEUED or RUNNING status"
            )

    def raise_not_in_completed_status(self):
        if self.status != "SUCCESS":
            raise ValueError(f"Experiment in status {self.status} is not in SUCCESS status")

    def cancel_provider_batch(self):
        self.client.batch.jobs.cancel(job_id=self.batch_id)

    def delete_provider_batch(self):
        if self.batch.status in ["QUEUED", "RUNNING"]:
            self.cancel_provider_batch()
        elif self.batch.status == "SUCCESS" and self.batch.output_file_id:
            self.delete_provider_file(file_id=self.batch.output_file_id)

    def get_provider_results(self) -> Response:
        return self.client.files.download(self.batch.output_file)
