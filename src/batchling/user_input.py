import typing as t

from pydantic import BaseModel


class RawMessage(BaseModel):
    role: t.Literal["system", "user", "assistant"]
    content: str


class RawBody(BaseModel):
    messages: list[RawMessage]


class RawFile(BaseModel):
    content: list[RawBody]
