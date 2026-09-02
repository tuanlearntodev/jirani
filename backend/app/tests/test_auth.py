import json
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.role_enum import RoleEnum
from app.repositories.auth_repo import AuthRepo
from app.schemas.account_schema import AccountCreateRequest
from app.services.auth_service import AuthService
from app.tests.conftest import auth_headers, login, setup_admin

# --- Helpers ---


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


def _create_students(
    client: TestClient, token: str, count: int, prefix: str
) -> list[dict[str, Any]]:
    response = client.post(
        "/auth/users/bulk",
        json={"count": count, "role": "student", "prefix": prefix},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return cast(list[dict[str, Any]], response.json()["accounts"])


def _account_id(client: TestClient, token: str, username: str) -> int:
    users = client.get("/auth/users", headers=auth_headers(token)).json()
    for u in users:
        if u["username"] == username:
            account_id = u["id"]
            assert isinstance(account_id, int)
            return account_id
    raise AssertionError(f"Account with username '{username}' not found.")


# --- Service level (AuthService + db fixture) ---


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


# --- Repo level (AuthRepo + db fixture) ---


def test_repo_get_by_username_found(db: Session) -> None:
    hashed_password = service_for(db).get_password_hash("testpassword")
    account = AuthRepo(db).create_account(
        Account(
            username="testuser",
            hashed_password=hashed_password,
            role=RoleEnum.student,
            first_name="Test",
            last_name="User",
        )
    )

    assert account.id is not None

    found = AuthRepo(db).get_by_username("testuser")

    assert found is not None
    assert found.id == account.id
    assert found.username == "testuser"


def test_repo_get_by_username_not_found(db: Session) -> None:
    hashed_password = service_for(db).get_password_hash("testpassword")
    account = AuthRepo(db).create_account(
        Account(
            username="testuser",
            hashed_password=hashed_password,
            role=RoleEnum.student,
            first_name="Test",
            last_name="User",
        )
    )

    assert account.id is not None

    found = AuthRepo(db).get_by_username("missing")

    assert found is None


def test_repo_get_by_id_found_and_missing(db: Session) -> None:
    hashed_password = service_for(db).get_password_hash("testpassword")
    account = AuthRepo(db).create_account(
        Account(
            username="testuser",
            hashed_password=hashed_password,
            role=RoleEnum.student,
            first_name="Test",
            last_name="User",
        )
    )

    assert account.id is not None

    found = AuthRepo(db).get_by_id(account.id)
    missing = AuthRepo(db).get_by_id(999999)

    assert found is not None
    assert found.id == account.id
    assert missing is None


def test_repo_get_all_users_filters_by_role(db: Session) -> None:
    hashed_password = service_for(db).get_password_hash("testpassword")
    for name, role in [
        ("student", RoleEnum.student),
        ("teacher", RoleEnum.teacher),
    ]:
        account = AuthRepo(db).create_account(
            Account(
                username=name,
                hashed_password=hashed_password,
                role=role,
                first_name=name,
                last_name="User",
            )
        )
    assert account is not None

    all_users = AuthRepo(db).get_all_users()
    student_accounts = AuthRepo(db).get_all_users(role=RoleEnum.student)

    assert [u.username for u in all_users] == ["student", "teacher"]
    assert [u.username for u in student_accounts] == ["student"]


def test_repo_next_prefix_empty(db: Session) -> None:
    next_prefix = AuthRepo(db).get_next_prefix_number("stu")
    assert next_prefix == 1


def test_repo_next_prefix_continues_from_max(db: Session) -> None:
    hashed_password = service_for(db).get_password_hash("testpassword")
    for user_name in ["stu001", "stu002", "stu003", "stu004", "stu005"]:
        AuthRepo(db).create_account(
            Account(
                username=user_name,
                hashed_password=hashed_password,
                role=RoleEnum.student,
                first_name=user_name,
                last_name="User",
            )
        )

    next_prefix = AuthRepo(db).get_next_prefix_number("stu")
    assert next_prefix == 6


def test_repo_next_prefix_ignores_non_digit_suffix(db: Session) -> None:
    hashed_password = service_for(db).get_password_hash("testpassword")
    AuthRepo(db).create_account(
        Account(
            username="stuabc",
            hashed_password=hashed_password,
            role=RoleEnum.student,
            first_name="stuabc",
            last_name="User",
        )
    )

    next_prefix = AuthRepo(db).get_next_prefix_number("stu")

    assert next_prefix == 1


def test_repo_change_password_first_login_default_false(db: Session) -> None:
    hashed_password = service_for(db).get_password_hash("testpassword")
    teacher = AuthRepo(db).create_account(
        Account(
            username="teacher",
            hashed_password=hashed_password,
            role=RoleEnum.teacher,
            first_name="Teacher",
            last_name="User",
        )
    )

    assert teacher.first_login is True

    new_hashed_password = service_for(db).get_password_hash("newpassword")
    AuthRepo(db).change_password(teacher, new_hashed_password)

    assert teacher.hashed_password == new_hashed_password
    assert teacher.first_login is False


def test_repo_change_password_can_keep_first_login(db: Session) -> None:
    hashed_password = service_for(db).get_password_hash("testpassword")
    teacher = AuthRepo(db).create_account(
        Account(
            username="teacher",
            hashed_password=hashed_password,
            role=RoleEnum.teacher,
            first_name="Teacher",
            last_name="User",
        )
    )

    assert teacher.first_login is True

    new_hashed_password = service_for(db).get_password_hash("newpassword")
    AuthRepo(db).change_password(teacher, new_hashed_password, first_login=True)

    assert teacher.hashed_password == new_hashed_password
    assert teacher.first_login is True


# --- HTTP level (client fixture) ---


def test_client_boots(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Welcome to Jirani Offline Library Backend"


def test_reset_teacher_password_as_teacher_is_403(
    client: TestClient, setup_paths: Path
) -> None:
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]

    actor_pw = _create_teacher(client, token, "actor")
    actor_token = login(client, "actor", actor_pw)["access_token"]
    _create_teacher(client, token, "victim")
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


def test_admin_reset_of_student_keeps_first_login_true(
    client: TestClient, setup_paths: Path
) -> None:
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]

    student = _create_students(client, token, 1, "victim")[0]
    victim_id = _account_id(client, token, student["username"])
    response = client.post(
        "/auth/reset-password",
        json={"account_id": victim_id},
        headers=auth_headers(token),
    )

    assert response.status_code == 200, response.text

    new_password = response.json()["new_password"]
    assert isinstance(new_password, str)

    victim_login = login(client, student["username"], new_password)
    assert victim_login["first_login"] is True


def test_admin_reset_of_teacher_returns_default_password(
    client: TestClient, setup_paths: Path
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
    assert response.json()["new_password"] == "teacher123"


def test_create_teacher_returns_default_password(
    client: TestClient, setup_paths: Path
) -> None:
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]

    credential = _create_teacher(client, token, "teacher")
    assert credential == "teacher123"


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


def test_setup_first_visit_generates_admin(
    client: TestClient, setup_paths: Path
) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    stored_credentials = json.loads((setup_paths / ".credentials").read_text())[
        "password"
    ]

    assert isinstance(stored_credentials, str)
    assert admin_pwd == stored_credentials


def test_setup_second_visit_returns_403(client: TestClient, setup_paths: Path) -> None:
    setup_admin(client, setup_paths)
    response = client.get("/setup")
    assert response.status_code == 403, response.text


def test_login_admin_success(client: TestClient, setup_paths: Path) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = client.post(
        "/auth/token", json={"username": "admin", "password": admin_pwd}
    )
    assert token.status_code == 200
    assert token.json()["username"] == "admin"
    assert token.json()["role"] == "admin"


def test_login_teacher_first_login_true(client: TestClient, setup_paths: Path) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    teacher_pwd = _create_teacher(client, token, "teacher")
    first_login = login(client, "teacher", teacher_pwd)["first_login"]

    assert first_login is True


def test_login_student_first_login_true(client: TestClient, setup_paths: Path) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    student = _create_students(client, token, 1, "student")
    student_first_login = login(client, student[0]["username"], student[0]["password"])[
        "first_login"
    ]

    assert student_first_login is True


def test_login_wrong_password_is_401(client: TestClient, setup_paths: Path) -> None:
    setup_admin(client, setup_paths)
    response = client.post(
        "/auth/token", json={"username": "admin", "password": "wrong_password"}
    )

    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient, setup_paths: Path) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]
    response = client.get("/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["username"] == "admin"
    assert response.json()["role"] == "admin"


def test_me_without_token_rejected(client: TestClient, setup_paths: Path) -> None:
    setup_admin(client, setup_paths)
    response = client.get("/auth/me")
    assert response.status_code in [401, 403]


def test_create_student_by_admin(client: TestClient, setup_paths: Path) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    response = client.post(
        "/auth/users",
        json={
            "username": "student1",
            "role": "student",
            "first_name": "Student",
            "last_name": "One",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["username"] == "student1"
    assert response.json()["credential"] == "student123"


def test_create_admin_by_admin_is_400(client: TestClient, setup_paths: Path) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    response = client.post(
        "/auth/users",
        json={
            "username": "admin1",
            "password": "password1",
            "role": "admin",
            "first_name": "Admin",
            "last_name": "One",
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 400, response.text


def test_create_teacher_by_teacher_is_403(
    client: TestClient, setup_paths: Path
) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    actor_pw = _create_teacher(client, token, "actor")
    actor_token = login(client, "actor", actor_pw)["access_token"]
    response = client.post(
        "/auth/users",
        json={
            "username": "victim",
            "role": "teacher",
            "first_name": "Victim",
            "last_name": "One",
        },
        headers=auth_headers(actor_token),
    )

    assert response.status_code == 403, response.text


def test_create_duplicate_username_is_400(
    client: TestClient, setup_paths: Path
) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    _create_teacher(client, token, "actor")
    response = client.post(
        "/auth/users",
        json={
            "username": "actor",
            "role": "teacher",
            "first_name": "Teacher",
            "last_name": "One",
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 400, response.text


def test_bulk_create_students_by_admin(client: TestClient, setup_paths: Path) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    accounts = _create_students(client, token, 3, "bu")

    assert [account["username"] for account in accounts] == ["bu001", "bu002", "bu003"]


def test_bulk_create_teacher_by_teacher(client: TestClient, setup_paths: Path) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    teacher_pwd = _create_teacher(client, token, "teacher")
    teacher_token = login(client, "teacher", teacher_pwd)["access_token"]

    response = client.post(
        "/auth/users/bulk",
        json={"count": 3, "role": "teacher", "prefix": "te"},
        headers=auth_headers(teacher_token),
    )
    assert response.status_code == 403, response.text


def test_bulk_create_admin_is_400(client: TestClient, setup_paths: Path) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    response = client.post(
        "/auth/users/bulk",
        json={"count": 3, "role": "admin", "prefix": "ad"},
        headers=auth_headers(token),
    )
    assert response.status_code == 400, response.text


def test_student_changes_own_password_then_relogin(
    client: TestClient, setup_paths: Path
) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    student = _create_students(client, token, 1, "stu")[0]

    student_token = login(client, student["username"], student["password"])[
        "access_token"
    ]

    change_password = client.post(
        "/auth/change-password",
        json={"old_password": student["password"], "new_password": "new_password"},
        headers=auth_headers(student_token),
    )

    assert change_password.status_code == 200, change_password.text

    reponse = client.post(
        "/auth/token",
        json={"username": student["username"], "password": "new_password"},
    )

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["first_login"] is False


def test_change_password_wrong_old_password_is_400(
    client: TestClient, setup_paths: Path
) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    student = _create_students(client, token, 1, "stu")[0]

    student_token = login(client, student["username"], student["password"])[
        "access_token"
    ]

    response = client.post(
        "/auth/change-password",
        json={"old_password": "wrong_password", "new_password": "new_password"},
        headers=auth_headers(student_token),
    )
    assert response.status_code == 400, response.text


def test_change_password_sets_first_login_false(
    client: TestClient, setup_paths: Path
) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    student = _create_students(client, token, 1, "stu")[0]
    student_token = login(client, student["username"], student["password"])[
        "access_token"
    ]

    client.post(
        "/auth/change-password",
        json={"old_password": student["password"], "new_password": "new_password"},
        headers=auth_headers(student_token),
    )

    response = client.get("/auth/me", headers=auth_headers(student_token))

    assert response.status_code == 200
    assert response.json()["first_login"] is False


def test_teacher_resets_student_password(client: TestClient, setup_paths: Path) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    teacher_pwd = _create_teacher(client, token, "teacher")
    teacher_token = login(client, "teacher", teacher_pwd)["access_token"]

    student = _create_students(client, token, 1, "student")[0]
    student_id = _account_id(client, token, student["username"])

    change_pwd_response = client.post(
        "/auth/reset-password",
        json={"account_id": student_id},
        headers=auth_headers(teacher_token),
    )
    assert change_pwd_response.status_code == 200, change_pwd_response.text

    login_reponse = client.post(
        "/auth/token",
        json={
            "username": "student001",
            "password": change_pwd_response.json()["new_password"],
        },
    )

    assert login_reponse.status_code == 200, login_reponse.text


def test_reset_missing_account_is_404(client: TestClient, setup_paths: Path) -> None:
    admin_pwd = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pwd)["access_token"]

    response = client.post(
        "/auth/reset-password", json={"account_id": 3}, headers=auth_headers(token)
    )
    assert response.status_code == 404, response.text
