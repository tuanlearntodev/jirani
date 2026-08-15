import json
from collections.abc import Generator
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

DBEnv = tuple[FastAPI, ModuleType]


@pytest.fixture(scope="session")
def db_env() -> Generator[DBEnv]:
    import app.api.setup_router as setup_router_module
    import app.main

    yield app.main.app, setup_router_module


@pytest.fixture(autouse=True)
def reset_db(db_env: DBEnv) -> Generator[None]:
    from app.database import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client(db_env: DBEnv) -> Generator[TestClient]:
    app, _ = db_env
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db(db_env: DBEnv) -> Generator[Session]:
    from app.database import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def setup_paths(db_env: DBEnv, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    _, setup_router_module = db_env
    monkeypatch.setattr(setup_router_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        setup_router_module, "CREDENTIALS_FILE", tmp_path / ".credentials"
    )
    monkeypatch.setattr(
        setup_router_module, "REVEALED_FLAG", tmp_path / ".credentials_revealed"
    )
    return tmp_path


def _read_admin_password(paths: Path) -> str:
    password = json.loads((paths / ".credentials").read_text())["password"]
    assert isinstance(password, str)
    return password


def setup_admin(client: TestClient, paths: Path) -> str:
    response = client.get("/setup")
    assert response.status_code == 200
    return _read_admin_password(paths)


def login(client: TestClient, username: str, password: str) -> dict[str, Any]:
    response = client.post(
        "/auth/token", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
