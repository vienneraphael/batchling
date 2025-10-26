import typing as t

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class GeminiUploadResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProviderFile(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(validation_alias=AliasChoices("id", "name"))

    @model_validator(mode="before")
    @classmethod
    def unify_nested_fields(cls, data: t.Any):
        if not isinstance(data, dict):
            return data
        file = data.get("file")
        if isinstance(file, dict):
            return file
        return data


class ProviderBatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = Field(default=None, validation_alias=AliasChoices("id", "name"))
    status: str = Field(
        default="created", validation_alias=AliasChoices("status", "processing_status")
    )
    output_file_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("output_file_id", "output_file", "results_url"),
    )

    @model_validator(mode="before")
    @classmethod
    def unify_nested_fields(cls, data: t.Any):
        if not isinstance(data, dict):
            return data
        metadata = data.get("metadata")
        if isinstance(metadata, dict) and "state" in metadata:
            data["status"] = metadata.get("state")
        job = data.get("job")
        if isinstance(job, dict) and "id" in job:
            return job
        return data
