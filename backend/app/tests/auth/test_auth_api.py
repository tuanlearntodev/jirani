import json
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.conftest import auth_headers, login, setup_admin


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
