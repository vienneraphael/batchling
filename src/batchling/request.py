import typing as t

from pydantic import BaseModel, Field, TypeAdapter, model_validator


class RawMessage(BaseModel):
    role: t.Literal["user", "assistant"]
    content: str | list[dict]


class RawRequest(BaseModel):
    system_prompt: str = "You are a helpful assistant."
    messages: list[RawMessage]
    max_tokens: int | None = None


raw_request_list_adapter = TypeAdapter(list[RawRequest])


class ProcessedMessage(RawMessage):
    role: t.Literal["system", "user", "assistant"]
    content: str | list[dict]


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
    reasoning_effort: str | None = None


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


class GeminiBlob(BaseModel):
    mime_type: str
    data: str

    @classmethod
    def from_bytes_str(cls, bytes_str: str) -> "GeminiBlob":
        mime_type, bytes_data = bytes_str.split(";base64,")
        mime_type = mime_type.strip("data:")
        return cls(mime_type=mime_type, data=bytes_data)


class GeminiPart(BaseModel):
    text: str | None = None
    inline_data: GeminiBlob | None = None

    @model_validator(mode="before")
    @classmethod
    def check_one_of_fields(cls, data: t.Any) -> t.Any:
        if data.get("text") is not None and data.get("inline_data") is not None:
            raise ValueError("Only one of text or inline_data can be provided")
        return data

    @model_validator(mode="before")
    @classmethod
    def check_required_fields(cls, data: t.Any) -> t.Any:
        if data.get("text") is None and data.get("inline_data") is None:
            raise ValueError("One of text or inline_data must be provided")
        return data


class GeminiConfig(BaseModel):
    response_mime_type: t.Literal["application/json", "text/plain"]
    response_json_schema: dict | None = None
    thinking_config: dict | None = None


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
    thinking: dict | None = None

    @model_validator(mode="after")
    def validate_thinking(self) -> "AnthropicBody":
        if self.thinking is not None:
            if "thinking_budget" in self.thinking:
                budget = self.thinking["thinking_budget"]
                self.thinking = {"type": "enabled", "budget_tokens": budget}
            elif "thinking_level" in self.thinking:
                raise ValueError("thinking_level is not supported for Anthropic")
        return self


class AnthropicRequest(BaseModel):
    custom_id: str
    params: AnthropicBody
