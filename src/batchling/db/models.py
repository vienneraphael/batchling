import typing as t
from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Experiment(Base):
    __tablename__ = "experiments"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    uid: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[t.Literal["openai", "mistral", "together", "groq", "gemini", "anthropic"]] = (
        mapped_column(String, nullable=False)
    )
    endpoint: Mapped[str | None] = mapped_column(String, nullable=True)
    api_key: Mapped[str] = mapped_column(String, nullable=False)
    raw_requests: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    processed_requests: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    response_format: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    processed_file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    results_file_path: Mapped[str] = mapped_column(String, nullable=False)
    provider_file_id: Mapped[str | None] = mapped_column(String, nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String, nullable=True)
