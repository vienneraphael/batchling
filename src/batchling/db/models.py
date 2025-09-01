import typing as t
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[t.Literal["openai", "mistral", "together", "groq", "gemini", "anthropic"]] = (
        mapped_column(String, nullable=False)
    )
    endpoint: Mapped[str | None] = mapped_column(String, nullable=True)
    api_key_name: Mapped[str] = mapped_column(String, nullable=False)
    template_messages: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    placeholders: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    response_format: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    max_tokens_per_request: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    output_file_path: Mapped[str] = mapped_column(String, nullable=False)
    input_file_id: Mapped[str | None] = mapped_column(String, nullable=True)
    is_setup: Mapped[bool] = mapped_column(Boolean, nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String, nullable=True)
