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


class TogetherBody(Body):
    model: str
    response_format: dict | None = None


class TogetherRequest(Request):
    body: TogetherBody


class GeminiPart(BaseModel):
    text: str


class GeminiConfig(BaseModel):
    response_mime_type: str
    response_schema: dict | None = None


class GeminiMessage(BaseModel):
    role: t.Literal["user", "assistant"] | None = None
    parts: list[GeminiPart]


class GeminiSystemInstructions(BaseModel):
    parts: list[GeminiPart]


class GeminiBody(Body):
    system_instructions: GeminiSystemInstructions | None = None
    messages: list[GeminiMessage] = Field(alias="contents")
    config: GeminiConfig | None = None


class GeminiRequest(Request):
    custom_id: str = Field(alias="key")
    body: GeminiBody = Field(alias="request")


class AnthropicBody(Body):
    model: str
    max_tokens: int | None = None
    messages: list[Message]
    response_format: dict | None = None


class AnthropicRequest(Request):
    body: AnthropicBody = Field(alias="params")
