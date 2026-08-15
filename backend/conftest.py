import os

import pytest
from testcontainers.community.postgres import PostgresContainer

POSTGRES_IMAGE = "postgres:16-alpine"

_postgres_container: PostgresContainer | None = None


@pytest.hookimpl()
def pytest_sessionstart(session: pytest.Session) -> None:
    global _postgres_container
    _postgres_container = PostgresContainer(POSTGRES_IMAGE)
    _postgres_container.start()
    os.environ["DATABASE_URL"] = _postgres_container.get_connection_url()
    os.environ["SECRET_KEY"] = "test-secret-key"


@pytest.hookimpl()
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    global _postgres_container
    if _postgres_container is not None:
        _postgres_container.stop()
        _postgres_container = None
