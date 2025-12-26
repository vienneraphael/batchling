import json
import typing as t

import structlog
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

log = structlog.get_logger(__name__)


class BatchResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = None
    custom_id: str | None = None
    answer: str | None
    model: str | None = None
    original: dict

    @classmethod
    def from_provider_response(cls, provider: str, data: dict) -> "BatchResult":
        log.debug("Generating BatchResult from provider response", provider=provider, data=data)
        if provider == "gemini":
            return cls(
                id=data.get("response", {}).get("responseId"),
                custom_id=data.get("key"),
                answer=data.get("response", {})
                .get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text"),
                model=data.get("response", {}).get("modelVersion"),
                original=data,
            )
        elif provider == "anthropic":
            content = data.get("result", {}).get("message", {}).get("content", [{}])
            answer = None
            for c in content:
                if c.get("type") == "text":
                    answer = c.get("text")
                    break
            if answer is None:
                answer = json.dumps(
                    data.get("result", {}).get("message", {}).get("content", [{}])[0].get("input")
                )
            return cls(
                id=data.get("result", {}).get("message", {}).get("id"),
                custom_id=data.get("custom_id"),
                answer=answer,
                model=data.get("result", {}).get("message", {}).get("model"),
                original=data,
            )
        else:
            return cls(
                id=data.get("id"),
                custom_id=data.get("custom_id"),
                answer=data.get("response", {})
                .get("body", {})
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content"),
                model=data.get("response", {}).get("body", {}).get("model"),
                original=data,
            )


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

    id: str = Field(validation_alias=AliasChoices("id", "name"))
    status: str = Field(
        default="created", validation_alias=AliasChoices("status", "processing_status")
    )
    output_file_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("output_file_id", "output_file", "results_url"),
    )
    error_file_id: str | None = Field(default=None, validation_alias=AliasChoices("error_file"))

    @model_validator(mode="before")
    @classmethod
    def unify_nested_fields(cls, data: t.Any):
        if not isinstance(data, dict):
            return data
        metadata = data.get("metadata")
        if isinstance(metadata, dict) and "state" in metadata:
            data["status"] = metadata.get("state")
        response = data.get("response")
        if isinstance(response, dict) and response.get("responsesFile"):
            data["output_file_id"] = response.get("responsesFile")
        job = data.get("job")
        if isinstance(job, dict) and "id" in job:
            return job
        return data
