"""Shared API test fixtures.

The suite runs against PostgreSQL inside Compose and falls back to an in-memory
SQLite database for a fast local smoke run. PostgreSQL-only behaviour (row
locking under concurrency) is skipped on the SQLite fallback.
"""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_SECRET", "test-secret-that-is-long-enough-for-tests")
os.environ.setdefault("COOKIE_SECURE", "false")

TEST_DATABASE_URL = os.environ.get("DATABASE_URL")
if TEST_DATABASE_URL is None and os.environ.get("DATABASE_HOST"):
    TEST_DATABASE_URL = URL.create(
        "postgresql+psycopg",
        username=os.environ.get("DATABASE_USER", "booker"),
        password=os.environ.get("DATABASE_PASSWORD", ""),
        host=os.environ["DATABASE_HOST"],
        port=int(os.environ.get("DATABASE_PORT", "5432")),
        database=os.environ.get("DATABASE_NAME", "booker_tpv_test"),
    ).render_as_string(hide_password=False)
TEST_DATABASE_URL = TEST_DATABASE_URL or "sqlite+pysqlite:///:memory:"
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, User, UserRole  # noqa: E402
from app.security import hash_password  # noqa: E402

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False} if TEST_DATABASE_URL.startswith("sqlite") else {},
    poolclass=StaticPool if TEST_DATABASE_URL.endswith(":memory:") else None,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

PASSWORDS = {
    "admin": "test-admin-password",
    "cashier": "test-cashier-password",
    "supervisor": "test-supervisor-password",
}


def reset_schema() -> None:
    """Recreate the isolated test schema so failed runs cannot leak DDL state."""
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    else:
        Base.metadata.drop_all(engine)


def sign_in(client: TestClient, username: str) -> TestClient:
    """Authenticate the test client with a seeded account."""
    response = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORDS[username]})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """Provide an isolated schema and seeded staff accounts per test."""
    reset_schema()
    Base.metadata.create_all(engine)

    def override_get_db() -> Generator[Session, None, None]:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestingSession() as session:
        session.add_all([
            User(username=username, password_hash=hash_password(password), role=role)
            for username, password, role in (
                ("admin", PASSWORDS["admin"], UserRole.ADMIN),
                ("cashier", PASSWORDS["cashier"], UserRole.CASHIER),
                ("supervisor", PASSWORDS["supervisor"], UserRole.SUPERVISOR),
            )
        ])
        session.commit()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    reset_schema()


@pytest.fixture()
def admin(client: TestClient) -> Generator[TestClient, None, None]:
    """Return an independent client authenticated as administrator."""
    del client
    with TestClient(app) as admin_client:
        yield sign_in(admin_client, "admin")


@pytest.fixture()
def supervisor(client: TestClient) -> Generator[TestClient, None, None]:
    """Return an independent client authenticated as supervisor."""
    del client
    with TestClient(app) as supervisor_client:
        yield sign_in(supervisor_client, "supervisor")


@pytest.fixture()
def cashier(client: TestClient) -> Generator[TestClient, None, None]:
    """Return an independent client authenticated as cashier."""
    del client
    with TestClient(app) as cashier_client:
        yield sign_in(cashier_client, "cashier")


@pytest.fixture()
def postgres_only() -> None:
    """Skip tests whose correctness depends on PostgreSQL row locking."""
    if engine.dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL row-level locking")
