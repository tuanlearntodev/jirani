from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.role_enum import RoleEnum
from app.repositories.auth_repo import AuthRepo
from app.schemas.account_schema import AccountCreateRequest
from app.services.auth_service import AuthService
from app.tests.conftest import auth_headers, login, setup_admin


def service_for(db: Session) -> AuthService:
    return AuthService(AuthRepo(db))


def _create_teacher(client: TestClient, token: str, username: str) -> str:
    response = client.post(
        "/auth/users",
        json={
            "username": username,
            "role": "teacher",
            "first_name": "T",
            "last_name": "U",
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    credential = response.json()["credential"]
    assert isinstance(credential, str)
    return credential


def _account_id(client: TestClient, token: str, username: str) -> int:
    users = client.get("/auth/users", headers=auth_headers(token)).json()
    for u in users:
        if u["username"] == username:
            account_id = u["id"]
            assert isinstance(account_id, int)
            return account_id
    raise AssertionError(f"Account with username '{username}' not found.")


def test_client_boots(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Welcome to Jirani Offline Library Backend"


def test_verify_password_wrong_password_returns_false() -> None:
    hashed = AuthService.get_password_hash("right-password")
    assert AuthService.verify_password("wrong-password", hashed) is False


def test_verify_password_correct_returns_true() -> None:
    hashed = AuthService.get_password_hash("right-password")
    assert AuthService.verify_password("right-password", hashed) is True


def test_create_admin_via_service_raises_value_error(db: Session) -> None:
    with pytest.raises(ValueError):
        service_for(db).create_user(
            AccountCreateRequest(
                username="admin",
                role=RoleEnum.admin,
                first_name="Admin",
                last_name="User",
            ),
            user_role=RoleEnum.admin,
        )


def test_create_teacher_by_teacher_raises_permission_error(db: Session) -> None:
    with pytest.raises(PermissionError):
        service_for(db).create_user(
            AccountCreateRequest(
                username="teacher",
                role=RoleEnum.teacher,
                first_name="Teacher",
                last_name="User",
            ),
            user_role=RoleEnum.teacher,
        )


def test_create_teacher_by_admin_ok(db: Session) -> None:
    account, credential = service_for(db).create_user(
        AccountCreateRequest(
            username="teacher",
            role=RoleEnum.teacher,
            first_name="Teacher",
            last_name="User",
        ),
        user_role=RoleEnum.admin,
    )
    assert account.role == RoleEnum.teacher


def test_create_student_by_teacher_ok(db: Session) -> None:
    account, credential = service_for(db).create_user(
        AccountCreateRequest(
            username="student",
            role=RoleEnum.student,
            first_name="Student",
            last_name="User",
        ),
        user_role=RoleEnum.teacher,
    )
    assert account.role == RoleEnum.student


def test_student_self_change_accepts_4_char_word(db: Session) -> None:
    service_for(db).validate_credentials(
        RoleEnum.student, "cats", context="self_change"
    )


def test_student_self_change_rejects_3_chars(db: Session) -> None:
    with pytest.raises(ValueError):
        service_for(db).validate_credentials(
            RoleEnum.student, "cat", context="self_change"
        )


def test_reset_teacher_password_as_teacher_is_403(
    client: TestClient, setup_paths: Path
) -> None:
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]

    actor_pw = _create_teacher(client, token, "actor")
    _create_teacher(client, token, "victim")
    actor_token = login(client, "actor", actor_pw)["access_token"]

    victim_id = _account_id(client, token, "victim")
    response = client.post(
        "/auth/reset-password",
        json={"account_id": victim_id},
        headers=auth_headers(actor_token),
    )

    assert response.status_code == 403


def test_admin_reset_of_teacher_keeps_first_login_true(
    client: TestClient, setup_paths: Path, db: Session
) -> None:
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]

    _create_teacher(client, token, "victim")
    victim_id = _account_id(client, token, "victim")
    response = client.post(
        "/auth/reset-password",
        json={"account_id": victim_id},
        headers=auth_headers(token),
    )

    assert response.status_code == 200, response.text

    new_password = response.json()["new_password"]
    assert isinstance(new_password, str)

    victim_login = login(client, "victim", new_password)
    assert victim_login["first_login"] is True

    me = client.get("/auth/me", headers=auth_headers(victim_login["access_token"]))
    assert me.status_code == 200
    assert me.json()["first_login"] is True


def test_setup_returns_403_when_admin_exists_but_flag_missing(
    client: TestClient, setup_paths: Path
) -> None:
    setup_admin(client, setup_paths)
    (setup_paths / ".credentials_revealed").unlink()
    (setup_paths / ".credentials").unlink()
    response = client.get("/setup")

    assert response.status_code == 403, response.text


def test_bulk_prefix_with_percent_is_literal(
    client: TestClient, setup_paths: Path, db: Session
) -> None:
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]

    response = client.post(
        "/auth/users/bulk",
        json={"prefix": "a%1", "count": 2, "role": "student"},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    usernames = [a["username"] for a in response.json()["accounts"]]
    assert usernames == ["a%1001", "a%1002"]
