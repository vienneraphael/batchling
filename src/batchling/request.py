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


class GeminiSystemInstruction(BaseModel):
    parts: list[GeminiPart]


class GeminiBody(BaseModel):
    system_instruction: GeminiSystemInstruction | None = None
    contents: list[GeminiMessage]
    generation_config: GeminiConfig | None = None


class GeminiRequest(BaseModel):
    key: str
    request: GeminiBody


class AnthropicPart(BaseModel):
    type: t.Literal["text"]
    text: str


class AnthropicBody(Body):
    model: str
    max_tokens: int
    messages: list[Message]
    response_format: dict | None = None
    system: list[AnthropicPart] | None = None


class AnthropicRequest(BaseModel):
    custom_id: str
    params: AnthropicBody
