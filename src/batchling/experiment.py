import os
import typing as t
from datetime import datetime
from functools import cached_property

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


class Experiment(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)
    id: str = Field(description="experiment ID")
    name: str = Field(description="name of the experiment")
    description: str | None = Field(default=None, description="description of the experiment")
    model: str = Field(description="model to use")
    base_url: str | None = Field(
        default=None,
        description="base url of the used provider. Must be compatible with OAI Batch API. Defaults to OAI base url",
    )
    api_key: str | None = Field(
        default=None,
        description="API key for the used provider, uses OAI key from env variables by default",
    )
    template_messages: list[dict] | None = Field(
        default=None, description="messages template to use"
    )
    placeholders: list[dict] | None = Field(
        default=None, description="placeholders to map in the template messages"
    )
    response_format: BaseModel | None = Field(default=None, description="response model to use")
    input_file_path: str | None = Field(default=None, description="input file path")
    input_file: FileObject | None = Field(default=None, init=False, description="input file object")
    status_value: t.Literal["created", "setup"] = Field(
        default="created", description="status of the experiment"
    )
    batch: Batch | None = Field(default=None, init=False, description="batch object")
    created_at: datetime | None = Field(default=None, description="created at")
    updated_at: datetime | None = Field(default=None, description="updated at")

    def model_post_init(self, context):
        init_db()

    @computed_field
    @property
    def status(
        self,
    ) -> t.Literal[
        "created",
        "setup",
        "validating",
        "failed",
        "in_progress",
        "finalizing",
        "completed",
        "expired",
        "cancelling",
        "cancelled",
    ]:
        if self.batch is None:
            return self.status_value
        return self.batch.status

    @field_validator("created_at", "updated_at")
    def set_datetime(cls, value: datetime | None):
        return value or datetime.now()

    @field_validator("input_file_path")
    def check_jsonl_format(cls, value: str):
        """Check if the input file path is a .jsonl file

        Args:
            value (str): The input file path

        Returns:
            str: The input file path

        Raises:
            ValueError: If the input file path is not a .jsonl file
        """
        if isinstance(value, str):
            if not value.endswith(".jsonl"):
                raise ValueError("input_file_path must be a .jsonl file")
        return value

    @computed_field
    @cached_property
    def client(self) -> OpenAI:
        """Get the client

        Returns:
            OpenAI: The client
        """
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def write_jsonl_input_file(self) -> None:
        """Create the input file

        Returns:
            None

        Raises:
            ValueError: If the input file path is not a .jsonl file
        """
        write_input_batch_file(
            file_path=self.input_file_path,
            custom_id=self.id,
            model=self.model,
            messages=self.template_messages,
            response_format=self.response_format,
            placeholders=self.placeholders,
        )

    def setup(self) -> None:
        """Setup the experiment

        Returns:
            None
        """
        if self.status != "created":
            raise ValueError(f"Experiment in status {self.status} is not in created status")
        if not os.path.exists(self.input_file_path):
            self.write_jsonl_input_file()
        self.status_value = "setup"
        with get_db() as db:
            update_experiment(
                db=db, id=self.id, status_value=self.status_value, updated_at=datetime.now()
            )

    def start(self) -> Batch:
        """Start the experiment

        Returns:
            Batch: The batch object
        """
        if self.status != "setup":
            raise ValueError(f"Experiment in status {self.status} is not in setup status")
        self.input_file = self.client.files.create(
            file=open(self.input_file_path, "rb"), purpose="batch"
        )
        self.batch = self.client.batches.create(
            input_file_id=self.input_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"description": self.description},
        )
        self.status_value = "running"
        with get_db() as db:
            update_experiment(
                db=db, id=self.id, status_value=self.status_value, updated_at=datetime.now()
            )
        return self.batch

    def cancel(self) -> None:
        """Cancel the experiment

        Returns:
            None
        """
        if self.status != "running":
            raise ValueError(f"Experiment in status {self.status} is not in running status")
        self.client.batches.cancel(self.batch.id)
        self.status_value = "cancelled"
        with get_db() as db:
            update_experiment(
                db=db, id=self.id, status_value=self.status_value, updated_at=datetime.now()
            )

    def get_results(self) -> HttpxBinaryResponseContent:
        """Get the results of the experiment

        Returns:
            HttpxBinaryResponseContent: The results
        """
        return self.client.files.content(self.batch.output_file_id)

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

    def delete(self):
        with get_db() as db:
            delete_experiment(db=db, id=self.id)

    def update(self, **kwargs):
        if self.status != "created":
            raise ValueError(
                f"Can only update an experiment in created status. Found: {self.status}"
            )
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.save()
