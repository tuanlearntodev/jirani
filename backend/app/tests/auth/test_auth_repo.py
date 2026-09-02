import pytest
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.role_enum import RoleEnum
from app.repositories.auth_repo import AuthRepo
from app.schemas.account_schema import AccountCreateRequest
from app.services.auth_service import AuthService


def service_for(db: Session) -> AuthService:
    return AuthService(AuthRepo(db))


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
