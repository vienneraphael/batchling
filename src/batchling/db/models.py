from datetime import datetime

from sqlalchemy import JSON, DateTime, String
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
    base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    template_messages: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    placeholders: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    response_format: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    input_file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    input_file_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status_value: Mapped[str | None] = mapped_column(String, nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String, nullable=True)
