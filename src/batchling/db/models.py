from sqlalchemy import JSON, Column, DateTime, Enum, Integer, String
from sqlalchemy.orm import DeclarativeBase

from batchling.experiment import ExperimentStatus


class Base(DeclarativeBase):
    pass


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    model = Column(String, nullable=False)
    base_url = Column(String, nullable=True)
    api_key = Column(String, nullable=True)
    template_messages = Column(JSON, nullable=True)
    response_format = Column(JSON, nullable=True)
    input_file_path = Column(String, nullable=True)
    input_file_id = Column(String, nullable=True)
    status = Column(Enum(ExperimentStatus), nullable=True)
    batch_id = Column(String, nullable=True)
