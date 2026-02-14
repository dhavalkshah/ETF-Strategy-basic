import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

# Import main app and database Base
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.models import User, Instrument, HistoricalPrice, SymbolCache # Import all models for metadata

# Use SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def db_engine():
    """Yields a SQLAlchemy engine for the test database."""
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine) # Clean up after tests

@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator:
    """Yields a SQLAlchemy session for each test, rolling back after each."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session) -> TestClient:
    """Yields a TestClient for FastAPI, with mocked database dependency."""
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture
def test_user_data():
    """Returns data for creating a test user."""
    return {
        "email": "test@example.com",
        "password": "testpassword"
    }

@pytest.fixture
def test_user(db_session, test_user_data) -> User:
    """Creates and returns a test user in the database."""
    from app.crud.user import user as crud_user
    user_in = test_user_data
    user = crud_user.create(db_session, obj_in=user_in)
    return user

@pytest.fixture
def auth_token(client, test_user_data) -> str:
    """Logs in the test user and returns an authentication token."""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user_data["email"], "password": test_user_data["password"]},
    )
    assert response.status_code == 200
    return response.json()["access_token"]

@pytest.fixture
def authorized_client(client, auth_token) -> TestClient:
    """Yields a TestClient with an authorized header."""
    client.headers = {**client.headers, "Authorization": f"Bearer {auth_token}"}
    return client