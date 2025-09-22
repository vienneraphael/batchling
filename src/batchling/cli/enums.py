from enum import StrEnum


class OrderByFields(StrEnum):
    id = "id"
    name = "name"
    description = "description"
    created_at = "created_at"
    updated_at = "updated_at"


class Provider(StrEnum):
    openai = "openai"
    mistral = "mistral"
    together = "together"
    groq = "groq"
    gemini = "gemini"
    anthropic = "anthropic"
