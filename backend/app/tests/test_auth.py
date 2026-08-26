import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.role_enum import RoleEnum
from app.repositories.auth_repo import AuthRepo
from app.schemas.account_schema import AccountCreateRequest
from app.services.auth_service import AuthService


def service_for(db: Session) -> AuthService:
    return AuthService(AuthRepo(db))


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
