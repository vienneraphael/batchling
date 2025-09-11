import typing as t

from pydantic import BaseModel, Field, TypeAdapter


class RawMessage(BaseModel):
    role: t.Literal["user", "assistant"]
    content: str


class RawRequest(BaseModel):
    system_prompt: str = "You are a helpful assistant."
    messages: list[RawMessage]
    max_tokens: int | None = None


raw_request_list_adapter = TypeAdapter(list[RawRequest])


class ProcessedMessage(RawMessage):
    role: t.Literal["system", "user", "assistant"]
    content: str


class ProcessedBody(BaseModel):
    messages: list[ProcessedMessage]
    max_tokens: int | None = None


class ProcessedRequest(BaseModel):
    custom_id: str
    body: ProcessedBody


processed_request_list_adapter = TypeAdapter(list[ProcessedRequest])


class MistralBody(ProcessedBody):
    response_format: dict | None = None


class MistralRequest(ProcessedRequest):
    body: MistralBody


class OpenAIBody(ProcessedBody):
    model: str
    response_format: dict | None = None


class OpenAIRequest(ProcessedRequest):
    method: t.Literal["POST"] = Field(default="POST", init=False)
    url: str
    body: OpenAIBody


class GroqBody(ProcessedBody):
    model: str
    response_format: dict | None = None


class GroqRequest(ProcessedRequest):
    method: t.Literal["POST"] = Field(default="POST", init=False)
    url: str
    body: GroqBody


class TogetherBody(ProcessedBody):
    model: str
    response_format: dict | None = None


class TogetherRequest(ProcessedRequest):
    body: TogetherBody


class GeminiPart(BaseModel):
    text: str


class GeminiConfig(BaseModel):
    response_mime_type: t.Literal["application/json", "text/plain"]
    response_json_schema: dict | None = None


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


class AnthropicBody(BaseModel):
    model: str
    max_tokens: int
    messages: list[RawMessage]
    tools: list[dict] | None = None
    tool_choice: dict | None = None
    system: list[AnthropicPart] | None = None


class AnthropicRequest(BaseModel):
    custom_id: str
    params: AnthropicBody
