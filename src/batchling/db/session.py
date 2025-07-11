from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from platformdirs import user_data_dir
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from batchling.db.models import Base

APP_NAME = "batchling"
APP_AUTHOR = "batchling"

db_file_path = Path(user_data_dir(APP_NAME, APP_AUTHOR)) / f"{APP_NAME}.db"
db_file_path.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{db_file_path}", echo=False, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def destroy_db() -> None:
    Base.metadata.drop_all(bind=engine)
