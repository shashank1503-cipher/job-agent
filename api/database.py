import os
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

os.makedirs("output", exist_ok=True)
DATABASE_URL = "sqlite:///output/jobs.db"
engine = create_engine(
    DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI Depends generator."""
    with Session(engine) as session:
        yield session


@contextmanager
def db_session():
    """Context manager for script/pipeline use — same engine, no second connection."""
    with Session(engine) as session:
        yield session
