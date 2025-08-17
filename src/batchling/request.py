import typing as t

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: t.Literal["system", "user", "assistant"]
    content: str


class Body(BaseModel):
    messages: list[Message]
    max_tokens: int | None = None


class Request(BaseModel):
    custom_id: str
    body: Body


class MistralBody(Body):
    response_format: dict | None = None


class MistralRequest(Request):
    body: MistralBody


class OpenAIBody(Body):
    model: str
    response_format: dict | None = None


class OpenAIRequest(Request):
    method: t.Literal["POST"] = Field(default="POST", init=False)
    url: str
    body: OpenAIBody


class GroqBody(Body):
    model: str
    response_format: dict | None = None


class GroqRequest(Request):
    method: t.Literal["POST"] = Field(default="POST", init=False)
    url: str
    body: GroqBody
