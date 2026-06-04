# Auth System Redesign — Design Spec

**Date:** 2026-06-02  
**Project:** Jirani Offline Library Backend  
**Scope:** Auth system only (content endpoints handled separately)

---

## Context

The existing auth system has several problems that must be fixed before the project scales:

- `POST /auth/seed-roles` and `POST /auth/make-admin/{username}` are completely unprotected — anyone on the network can call them
- Self-registration (`POST /auth/signup`) gives users no role, leaving them in a broken state
- Password recovery uses a weak 6-digit numeric OTP that is never invalidated after use
- `POST /auth/change-password` incorrectly requires admin role — teachers and admins should be able to change their own password; students never change their own PIN
- The models use SQLAlchemy 1.x `Column()` style and Pydantic v1 `class Config` style
- Three tables (`accounts`, `roles`, `account_roles`) require two joins just to check a user's role

The system serves children in low-internet, low-digital-literacy environments. The redesign must be simple for children to use while keeping the admin panel protected.

---

## Design Decisions

### 1. Single Table: `accounts`

The `roles` and `account_roles` tables are removed entirely. A single `role` enum column is added directly to `accounts`. Each user has exactly one role.

**Rationale:** The role set is fixed and hierarchical (admin > teacher > student). No real use case requires a user to hold two roles simultaneously. Collapsing three tables into one eliminates all join overhead and simplifies every query.

### 2. Role Enum

```
RoleEnum: admin | teacher | student
```

Enforced as a Python `enum.Enum` and stored as a native DB enum column. No CheckConstraint needed.

### 3. Credential Policy (matched to digital literacy level)

| Role    | Initial credential     | Validation rule (on creation) | Validation rule (on self-change) | Set by         |
|---------|------------------------|-------------------------------|-----------------------------------|----------------|
| student | 6-digit auto-generated | exactly 6 digits              | min 4 chars, any characters       | system (auto)  |
| teacher | password               | 8–50 chars                    | 8–50 chars                        | admin          |
| admin   | password               | 8–50 chars                    | 8–50 chars                        | self or admin  |

When a teacher or admin creates a student account, the system **auto-generates** a 6-digit random number as the initial password. It is returned in the response so the teacher can write it down and hand it to the student.

Students **can change their own password** at any time via `POST /auth/change-password`. The new password must be at least 4 characters. This gives kids the freedom to pick something they can remember without being locked into a random number.

All credentials are stored as bcrypt hashes — same mechanism, different input validation. Credential rules are enforced in the service layer, not the DB.

### 4. Account Creation

- **Admin** can create accounts with any role (admin, teacher, student)
- **Teacher** can create student accounts only
- **No public self-registration** — the `POST /auth/signup` endpoint is removed

For **student** accounts, the system auto-generates a 6-digit random number as the initial password. The response includes this raw credential exactly once so it can be written down and handed to the student.

For **teacher** and **admin** accounts, the creator provides the password in the request body.

### 5. First Admin Bootstrap

The system uses a **one-time setup endpoint** (`GET /setup`) instead of environment variables for the first admin. This is designed for headless SBC deployment — the teacher connects their phone to the SBC's network, opens `http://<sbc-ip>/setup` in their browser, and sees the admin password exactly once.

**How it works:**
1. On first visit to `/setup`, the app generates a unique admin password using `secrets.token_urlsafe(8)`
2. The credentials are saved to a JSON file on disk (`/app/data/.credentials`)
3. A flag file (`/app/data/.credentials_revealed`) is created to prevent showing the password again
4. On subsequent visits, `/setup` returns 403 "Already configured"
5. If the data directory is wiped (hard reset), the next visit to `/setup` generates new credentials

**Recovery:** If the teacher forgets the password, they need physical access to the device to read the credentials file or delete the flag file to regenerate.

**No env vars needed** — `ADMIN_USERNAME` and `ADMIN_PASSWORD` are not required in the config.
ADMIN_USERNAME=          # required for seeding
ADMIN_PASSWORD=          # required for seeding; must meet 12-char admin rule
ADMIN_FIRST_NAME=        # optional; defaults to "Admin"
ADMIN_LAST_NAME=         # optional; defaults to "User"
```

### 6. Password / PIN Reset

| Caller  | Can reset                  | Endpoint                    |
|---------|----------------------------|-----------------------------|
| Admin   | Any user's password/PIN    | `POST /auth/reset-password` |
| Teacher | Students' PINs only        | `POST /auth/reset-password` |
| Admin   | Own password               | `POST /auth/change-password` |
| Teacher | Own password               | `POST /auth/change-password` |
| Student | Own password               | `POST /auth/change-password` |

When a teacher or admin resets a student's password, a new 6-digit random number is auto-generated and returned in the response.

When a student changes their own password, they provide the new password (min 4 chars) themselves.

Self-service recovery (OTP flow) is removed entirely. Children who forget their PIN ask their teacher.

### 7. Token

Single 8-hour JWT. No refresh token. Long enough to cover a full school day without requiring re-login mid-session. The token payload carries `sub` (username), `user_id`, and `role` (single string, not a list).

---

## Data Model

### `accounts` table

| Column            | Type        | Notes                                      |
|-------------------|-------------|--------------------------------------------|
| `id`              | Integer PK  |                                            |
| `username`        | String(50)  | unique, indexed                            |
| `hashed_password` | String      | bcrypt hash of password or PIN             |
| `first_name`      | String(50)  |                                            |
| `last_name`       | String(50)  |                                            |
| `role`            | RoleEnum    | `admin` / `teacher` / `student`            |
| `is_active`       | Boolean     | default True; admin can deactivate         |
| `created_at`      | DateTime    | set on insert                              |
| `updated_at`      | DateTime    | set on insert, updated on every change     |

Tables removed: `roles`, `account_roles`

### SQLAlchemy style

All models use SQLAlchemy 2.0 `Mapped[T]` + `mapped_column()` syntax. A shared `TimestampMixin` provides `created_at` and `updated_at` to any model that needs it.

---

## Schema Layer

All Pydantic schemas use `model_config = ConfigDict(from_attributes=True)` (Pydantic v2 style). No `class Config` blocks.

Schemas follow the layering pattern: `Base → Create → Read`.

Reusable `Annotated` types enforce credential rules at the schema boundary:

```python
StudentSelfChangePassword = Annotated[str, Field(min_length=4, max_length=50)]
StaffPassword             = Annotated[str, Field(min_length=8, max_length=50)]
UsernameStr               = Annotated[str, Field(min_length=3, max_length=50)]
```

`StaffPassword` applies to both teachers and admins. Student initial passwords are auto-generated (6 digits) in the service layer — no schema-level validation needed for creation.

### Schema inventory

| Schema               | Purpose                                         |
|----------------------|-------------------------------------------------|
| `AccountBase`        | Shared fields: username, first_name, last_name  |
| `AccountCreate`      | Input for `POST /auth/users`: adds role, password |
| `AccountRead`        | Response shape: adds id, role, is_active, created_at |
| `LoginRequest`       | username + password/PIN                         |
| `TokenResponse`      | access_token, token_type, username, role (str)  |
| `CreateUserResponse` | `AccountRead` + one-time `credential` field     |
| `ResetPasswordRequest` | username + new_password                       |
| `ChangePasswordRequest` | old_password + new_password (username from token) |

---

## API Endpoints

### Kept (modified)

| Method | Path                    | Auth required         | Change                                          |
|--------|-------------------------|-----------------------|-------------------------------------------------|
| POST   | `/auth/token`           | None                  | Response `roles: list` → `role: str`            |
| POST   | `/auth/reset-password`  | Admin or Teacher      | Teacher restricted to resetting students only   |
| POST   | `/auth/change-password` | Any authenticated     | Bug fix: was admin-only; now any user can change their own password (student: min 4 chars, teacher: 8+, admin: 12+) |

### New

| Method | Path           | Auth required     | Description                                              |
|--------|----------------|-------------------|----------------------------------------------------------|
| POST   | `/auth/users`  | Admin or Teacher  | Create a user; admin: any role, teacher: student only    |
| GET    | `/auth/users`  | Admin or Teacher  | List users; admin: all, teacher: students only           |
| GET    | `/auth/me`     | Any authenticated | Returns current user profile                             |

### Removed

| Method | Path                               | Reason                                      |
|--------|------------------------------------|---------------------------------------------|
| POST   | `/auth/signup`                     | No public self-registration                 |
| POST   | `/auth/seed-roles`                 | Security hole; replaced by `/setup` endpoint      |
| POST   | `/auth/make-admin/{username}`      | Security hole; use `POST /auth/users`       |
| POST   | `/auth/forgot-password/verify-code` | No self-service recovery                  |
| GET    | `/auth/admin-exists`               | Not needed with `/setup` endpoint           |

---

## Files Affected

### Modified
| File                              | Change                                                      |
|-----------------------------------|-------------------------------------------------------------|
| `app/models/account.py`           | Rewrite: SQLAlchemy 2.0 style, add `role`, timestamps       |
| `app/schemas/auth_schema.py`      | Rewrite: Pydantic v2, layered schemas, Annotated types      |
| `app/schemas/account_schema.py`   | Populate: AccountBase, AccountCreate, AccountRead           |
| `app/services/auth_service.py`    | Update: role-aware credential validation, new user creation |
| `app/dependencies/auth.py`        | Simplify RoleChecker: `current_user.role` not `.roles`      |
| `app/api/auth_router.py`          | Redesign: remove holes, add new endpoints                   |
| `app/config.py`                   | Rewrite: DATABASE_URL, SECRET_KEY from env, PostgreSQL-ready |
| `app/main.py`                     | Update: ensure data dir, register setup router              |

### Created
| File                              | Purpose                                                     |
|-----------------------------------|-------------------------------------------------------------|
| `app/models/role_enum.py`         | `RoleEnum` for admin/teacher/student                        |
| `app/models/base.py`              | `TimestampMixin` for shared timestamp columns               |
| `app/repositories/auth_repo.py`   | Database queries for auth                                   |
| `app/api/setup_router.py`         | `/setup` endpoint for one-time admin credential generation  |

### Deleted
| File                              | Reason                                                      |
|-----------------------------------|-------------------------------------------------------------|
| `app/models/role.py`              | Replaced by RoleEnum in account.py                          |
| `app/models/account_role.py`      | Merged into accounts table                                  |
| `app/scripts/create_admin.py`     | Replaced by `/setup` endpoint                               |
| `app/scripts/create_test_users.py` | Replaced by `POST /auth/users` endpoint                    |

---

## Out of Scope

- Content endpoint auth (book, video, audio routers) — separate plan
- Refresh tokens — not needed for this deployment context
- Email-based recovery — no internet access assumed
- Frontend implementation
