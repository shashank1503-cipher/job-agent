import pytest
from sqlmodel import SQLModel, Session, create_engine
from fastapi.testclient import TestClient

from api.main import app
from api.database import get_session
import api.database as db


@pytest.fixture
def test_engine():
    """Create a test engine with all tables."""
    engine = create_engine(
        "sqlite:///:memory:?uri=true&cache=shared",
        connect_args={"check_same_thread": False, "uri": True},
        echo=False,
    )
    SQLModel.metadata.create_all(engine)

    # Store original engine
    original_engine = db.engine
    db.engine = engine

    # Create override
    def override():
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()

    # Apply override
    app.dependency_overrides[get_session] = override

    yield engine

    # Restore
    db.engine = original_engine
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_engine):
    """Create a test client with test engine."""
    # Clear database before each test
    with Session(test_engine) as s:
        from sqlalchemy import delete
        from api.models import Job, Run

        s.exec(delete(Job))
        s.exec(delete(Run))
        s.commit()

    with TestClient(app) as c:
        yield c
