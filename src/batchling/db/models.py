from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase


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
    response_format = Column(JSON, nullable=True)
    input_file_path = Column(String, nullable=True)
    input_file_id = Column(String, nullable=True)
    status = Column(String, nullable=True)
    batch_id = Column(String, nullable=True)
