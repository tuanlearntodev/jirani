# Auth System Redesign — Implementation Plan (Learning Edition)

**Goal:** Redesign the auth system to be secure, simple for children, and follow modern Python best practices.

**Architecture:** Single `accounts` table with a `role` enum column; SQLAlchemy 2.0 `Mapped[]` models; Pydantic v2 layered schemas; admin/teacher-managed account creation; no public self-registration.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, python-jose (JWT), passlib (bcrypt), SQLite (dev)

**Spec:** `docs/specs/2026-06-02-auth-redesign-design.md`

> This plan is written for you to implement yourself. Each task gives you the **concept**, the **why**, and **hints** — not the finished code. Use the hints to guide your thinking. Verify your work at each step before moving on.

---

## How to read this plan

- Read the **Why** section before touching any code. Understanding the reason makes the code easier to write.
- The **Hints** section shows you partial examples and tells you what to look up — use them like a tutor, not a copy-paste source.
- The **Verify** step tells you what "done" looks like. Don't skip it.
- Commit after every task. Small commits = easy to undo mistakes.

---

## Important: SQLite schema reset

Because you are using SQLite with `Base.metadata.create_all()` (not Alembic), SQLAlchemy **cannot automatically update existing tables** when you change the model. It only creates tables that don't exist yet.

When you reach Task 3, you must delete the SQLite database file and let it rebuild from scratch:

```bash
# Find the db file (check config.py for DATABASE_URL)
rm backend/data/jirani_library.db   # adjust path if different
```

In a real production app, you would use **Alembic** to write migration scripts that modify the existing database safely. That is worth exploring after this project — search for "Alembic FastAPI tutorial".

---

## File Map

| File | Action | What changes |
|---|---|---|
| `app/models/role_enum.py` | **Create** | `RoleEnum` lives here |
| `app/models/base.py` | **Create** | `TimestampMixin` lives here |
| `app/models/account.py` | **Rewrite** | SQLAlchemy 2.0 style, add `role`, timestamps |
| `app/models/role.py` | **Delete** | Replaced by `RoleEnum` |
| `app/models/account_role.py` | **Delete** | Merged into `accounts` table |
| `app/models/__init__.py` | **Update** | Remove old imports |
| `app/schemas/auth_schema.py` | **Rewrite** | Pydantic v2 style, Annotated types |
| `app/schemas/account_schema.py` | **Populate** | Layered schemas: Base → Create → Read |
| `app/repositories/auth_repo.py` | **Create** | DB queries for auth (get_by_username, create, list, etc.) |
| `app/services/auth_service.py` | **Update** | Role-aware credential validation, uses AuthRepo |
| `app/dependencies/auth.py` | **Update** | Simplify `RoleChecker` for single-role model |
| `app/config.py` | **Rewrite** | Best-practice config: DATABASE_URL, SECRET_KEY from env, PostgreSQL-ready |
| `app/main.py` | **Update** | Startup: ensure upload dirs, no env var seeding |
| `app/api/auth_router.py` | **Rewrite** | Remove holes, add new endpoints including bulk creation |
| `app/api/setup_router.py` | **Create** | `/setup` endpoint — one-time admin credential generation |
| `app/scripts/create_admin.py` | **Delete** | Replaced by `/setup` endpoint |
| `app/scripts/create_test_users.py` | **Delete** | Replaced by `POST /auth/users` |
| `.env.example` | **Delete** | App is zero-config |
| `app/tests/test_auth.py` | **Create** | Tests for new auth endpoints |
| `app/tests/conftest.py` | **Create** | In-memory DB fixture for tests |

---

## Task 1: Read and understand the existing code

**Why:** You cannot safely change code you haven't read. This task has no output — it's pure reading. Take notes on anything that confuses you.

- [ ] Read `app/models/account.py`, `app/models/role.py`, `app/models/account_role.py` and draw (on paper or in a text file) how the three tables are related. What is the purpose of the junction table?

- [ ] Read `app/dependencies/auth.py`. Trace through `RoleChecker.__call__` line by line. Notice how it currently loops through `current_user.roles` (a list). After the redesign, `current_user.role` will be a single value. How will that simplify this code?

- [ ] Read `app/api/auth_router.py`. Find the two unprotected endpoints (`seed-roles`, `make-admin`). These have no `Depends(get_current_user)` — what does that mean security-wise?

- [ ] Read `app/services/auth_service.py`. Notice `create_user` assigns no role. Is that a bug or was it intentional?

- [ ] **No commit needed** — this task produces understanding, not code.

---

## Task 2: Create `RoleEnum`

**Why:** A Python `Enum` is the right tool for a fixed set of named values. It gives you autocompletion, type safety, and prevents typos like `"Admin"` vs `"admin"`. By combining `str` and `Enum`, the value behaves like a string (so it serializes naturally to JSON and stores in the DB as a plain string).

**Concept — Python Enum:**
```python
import enum

class Color(str, enum.Enum):
    red = "red"
    green = "green"
    blue = "blue"

# Usage
Color.red          # <Color.red: 'red'>
Color.red == "red" # True  <-- because it inherits from str
Color("red")       # <Color.red: 'red'>  <-- construct from string
```

**Hints:**
- Create a new file: `app/models/enums.py`
- Define `RoleEnum` with three members: `admin`, `teacher`, `student`
- Inherit from both `str` and `enum.Enum` (put `str` first)
- The `.value` of each member should be the lowercase string (`"admin"`, etc.)

**Verify:**
Open a Python REPL in the backend directory and test:
```python
from app.models.enums import RoleEnum
print(RoleEnum.admin)           # should print RoleEnum.admin
print(RoleEnum.admin == "admin") # should print True
print(RoleEnum("student"))      # should print RoleEnum.student
```

- [ ] Create `app/models/enums.py` with `RoleEnum`
- [ ] Verify in the REPL
- [ ] Commit: `git commit -m "feat: add RoleEnum for role management"`

---

## Task 3: Create `TimestampMixin`

**Why:** Many models (not just `Account`) will eventually need `created_at` and `updated_at`. Instead of copy-pasting those columns into every model, a **mixin** (a small class you mix into another class via inheritance) provides them in one place. This is the DRY principle (Don't Repeat Yourself).

**Concept — Python mixin with SQLAlchemy:**
SQLAlchemy mixins work through Python's multiple inheritance. Any class that inherits from the mixin gets its columns automatically. With SQLAlchemy 2.0 style, mixin columns use `Mapped[]` and `mapped_column()` just like a normal model.

**Hints:**
- Create `app/models/base.py`
- The mixin is a plain Python class (does NOT inherit from `Base`)
- Import `datetime` from Python's standard library for the type hint
- For `updated_at`, SQLAlchemy's `mapped_column` accepts an `onupdate=` argument — this is a function called automatically whenever a row is updated
- Use `datetime.utcnow` (the function itself, not `datetime.utcnow()` — without parentheses) as the `default` value
- Search for: "SQLAlchemy 2.0 mixin mapped_column"

**Key imports you will need:**
```python
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime
```

**Verify:**
The mixin is a class, not a model, so you can't run it independently yet. Just make sure the file has no import errors:
```bash
cd backend
python -c "from app.models.base import TimestampMixin; print('OK')"
```

- [ ] Create `app/models/base.py` with `TimestampMixin`
- [ ] Verify no import errors
- [ ] Commit: `git commit -m "feat: add TimestampMixin for shared timestamps"`

---

## Task 4: Rewrite the `Account` model (SQLAlchemy 2.0)

**Why:** SQLAlchemy 2.0 introduced `Mapped[T]` — a way to write model columns with proper Python type annotations. The old `Column(Integer, ...)` style works but provides no type information to your editor or type checker. With `Mapped[int]`, mypy and your IDE know exactly what type each column holds.

**Concept — SQLAlchemy 1.x vs 2.0 syntax:**
```python
# Old style (SQLAlchemy 1.x — what you have now)
id = Column(Integer, primary_key=True, index=True)
username = Column(String, unique=True, nullable=False)

# New style (SQLAlchemy 2.0)
id: Mapped[int] = mapped_column(primary_key=True, index=True)
username: Mapped[str] = mapped_column(String(50), unique=True)
```

The `Mapped[T]` annotation on the left tells Python (and tools like mypy) what type the attribute is. The `mapped_column()` on the right tells SQLAlchemy how to store it in the database.

**Concept — Storing an Enum in the database:**
SQLAlchemy has a special `Enum` type (from `sqlalchemy`) that stores your Python enum as a string in the DB. When you read it back, SQLAlchemy converts it back to your Python enum automatically.

```python
from sqlalchemy import Enum as SQLEnum
from app.models.enums import RoleEnum

role: Mapped[RoleEnum] = mapped_column(SQLEnum(RoleEnum), nullable=False)
```

**Hints for `app/models/account.py`:**
- Keep the file in `app/models/account.py` — just rewrite its contents
- Import `TimestampMixin` from `app.models.base` and add it to the class inheritance
- The class should inherit from BOTH `TimestampMixin` and `Base` (order matters — put `TimestampMixin` first)
- Remove `recovery_code_hash` — that feature is gone
- Remove the `roles` relationship — the role is now a single column, not a relationship
- Add `role: Mapped[RoleEnum]` column
- Add `created_at` and `updated_at` via the mixin (they come for free through inheritance)
- String columns: specify a max length in `String(50)` to be explicit

**What the model's columns should be:**
`id`, `username`, `hashed_password`, `first_name`, `last_name`, `role`, `is_active`, `created_at`, `updated_at`

**Verify:**
```bash
cd backend
python -c "from app.models.account import Account; print(Account.__table__.columns.keys())"
# Should print all the column names including 'role', 'created_at', 'updated_at'
# Should NOT include 'recovery_code_hash'
```

- [ ] Rewrite `app/models/account.py` in SQLAlchemy 2.0 style
- [ ] Verify column list
- [ ] Commit: `git commit -m "refactor: rewrite Account model in SQLAlchemy 2.0 style"`

---

## Task 5: Delete old model files and clean up imports

**Why:** Dead code is a liability. The `roles` and `account_roles` tables no longer exist in the design — keeping the files around means someone (future-you) might accidentally use them.

**Hints:**
- Delete `app/models/role.py`
- Delete `app/models/account_role.py`
- Open `app/models/__init__.py` — remove any imports of `Role` and `AccountRole`
- Open `app/models/__init__.py` — add an import for `RoleEnum` from `app.models.enums`
- Search the entire codebase for any remaining `from app.models.role import` or `from app.models.account_role import` and remove/fix them

**Find references:**
```bash
# Run from the backend/app directory
 
```

Fix every file that comes up.

**Verify:**
```bash
cd backend
python -c "from app.models import Account, RoleEnum; print('OK')"
# Must not raise ImportError
```

- [ ] Delete `app/models/role.py`
- [ ] Delete `app/models/account_role.py`
- [ ] Fix all imports
- [ ] Verify no import errors
- [ ] Commit: `git commit -m "refactor: remove Role and AccountRole models"`

---

## Task 6: Reset the database

**Why:** SQLAlchemy's `create_all()` is additive only — it creates tables that are missing but does NOT drop or alter existing tables. Your old DB has `roles` and `account_roles` tables, and the `accounts` table has the old schema. You must delete the file and let the app recreate it cleanly.

**This is normal in development.** In a production app, you would use Alembic migrations instead — but that's a separate learning topic.

- [ ] Find the database file path in `app/config.py` (look at `DATABASE_URL`)
- [ ] Delete the database file:
  ```bash
  # Example — adjust path to match your config
  rm /path/to/jirani_library.db
  ```
- [ ] Start the app and confirm it starts without errors (it will recreate the DB):
  ```bash
  cd backend
  uvicorn app.main:app --reload
  ```
- [ ] Open the Swagger UI at `http://localhost:8000/docs` — confirm the app loads
- [ ] Stop the server with Ctrl+C
- [ ] Commit: `git commit -m "chore: note db reset for schema migration"`

> **Tip:** Any time you change a model's columns during this plan, you'll need to delete the DB file again.

---

## Task 7: Rewrite auth schemas (Pydantic v2)

**Why:** Pydantic v2 changed its configuration style. The old `class Config` is still supported but deprecated — `model_config = ConfigDict(...)` is the modern way. More importantly, you'll learn the **Annotated type** pattern, which lets you define reusable validation rules for different credential types (student PIN vs teacher password vs admin password).

**Concept — Pydantic v2 `ConfigDict`:**
```python
# Old (Pydantic v1 style — what you have now)
class MySchema(BaseModel):
    class Config:
        from_attributes = True

# New (Pydantic v2 style)
from pydantic import BaseModel, ConfigDict

class MySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
```

**Concept — `Annotated` types for reusable validation:**
`Annotated` lets you attach metadata (like validation constraints) to a type. Combined with Pydantic's `Field`, this means you can define your validation rules once and reuse them:

```python
from typing import Annotated
from pydantic import Field

# Define once
UsernameStr = Annotated[str, Field(min_length=3, max_length=50)]

# Reuse in any schema
class LoginRequest(BaseModel):
    username: UsernameStr   # validation applied automatically
    password: str
```

**Hints for `app/schemas/auth_schema.py`:**
- At the top of the file, define these reusable types:
  - `UsernameStr` — min 3, max 50 chars
  - `StudentSelfChangePassword` — min 4, max 50 chars (for when a student changes their own password)
  - `StaffPassword` — min 8, max 50 chars (unified for both teachers and admins)
- Note: there is no `StudentPIN` type — student initial passwords are auto-generated in the service layer, not validated at the schema level
- Define these schemas (replace the entire file):
  - `LoginRequest`: `username: str`, `password: str` (no strict validation at login — wrong credentials get a 401, not a 422)
  - `TokenResponse`: `access_token: str`, `token_type: str = "bearer"`, `username: str`, `role: str` — note: `role` is now a single string, not a list
  - `ResetPasswordRequest`: `username: str`, `new_password: str`
  - `ChangePasswordRequest`: `old_password: str`, `new_password: str` (no `username` field — it comes from the token)
- Remove `SignUpRequest` entirely — no more public signup
- Remove `RoleSchema` — role is now a plain string/enum, not a model
- Remove `UserWithRoles` — that belongs in `account_schema.py` now

**Verify:**
```bash
cd backend
python -c "from app.schemas.auth_schema import LoginRequest, TokenResponse, ResetPasswordRequest, ChangePasswordRequest; print('OK')"
```

- [ ] Rewrite `app/schemas/auth_schema.py`
- [ ] Verify no import errors
- [ ] Commit: `git commit -m "refactor: rewrite auth schemas in Pydantic v2 style"`

---

## Task 8: Populate account schemas (layered schema pattern)

**Why:** The layered schema pattern (`Base → Create → Read`) is a best practice because:
- `Base` holds fields that are shared between input and output
- `Create` adds fields only needed on input (like `password`, `role`)
- `Read` adds fields only returned in responses (like `id`, `created_at`)

This prevents accidental data leaking (e.g., never accidentally returning `hashed_password`) and makes schemas self-documenting.

**Concept — Schema inheritance:**
```python
class AccountBase(BaseModel):
    username: str
    first_name: str
    last_name: str

class AccountCreate(AccountBase):
    password: str   # only needed on creation
    role: RoleEnum  # only needed on creation

class AccountRead(AccountBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: RoleEnum
    is_active: bool
    created_at: datetime
    # notice: no 'password' field — never expose it
```

**Hints for `app/schemas/account_schema.py`:**
- Import `RoleEnum` from `app.models.enums`
- Import `datetime` from Python's standard library
- Define `AccountBase` with the shared safe fields: `username`, `first_name`, `last_name`
- Define `AccountCreate(AccountBase)` — adds `password: str` and `role: RoleEnum`
  - Note: `password` validation (PIN vs password rules) is enforced in the *service layer*, not here, because the rule depends on the `role` value. At the schema level just accept any `str`.
- Define `AccountRead(AccountBase)` — adds `id`, `role`, `is_active`, `created_at`
  - Must have `model_config = ConfigDict(from_attributes=True)` so it can be built from a SQLAlchemy model instance
- Define `CreateUserResponse(AccountRead)` — adds `credential: str | None = None`
  - This is the one-time response when creating an account that includes the raw PIN/password

**Verify:**
```bash
cd backend
python -c "
from app.schemas.account_schema import AccountBase, AccountCreate, AccountRead, CreateUserResponse
from app.models.enums import RoleEnum
data = AccountCreate(username='test', first_name='A', last_name='B', password='1234', role=RoleEnum.student)
print(data)
"
```

- [ ] Populate `app/schemas/account_schema.py`
- [ ] Verify with the REPL snippet above
- [ ] Commit: `git commit -m "refactor: add layered account schemas"`

---

## Task 9: Create `AuthRepo`

**Why:** You already use the repository pattern for books (`BookRepo` + `BookService`). Using the same pattern for auth keeps the codebase consistent. The repo handles **database queries only** — no business logic, no validation, no hashing. The service layer does all that.

**Concept — Repository pattern:**
```
Router → Service (business logic: validation, hashing, tokens)
              ↓
         Repo (database queries only: get, create, list)
              ↓
          Database
```

This separation means:
- `AuthService` is easy to test (mock the repo)
- `AuthRepo` is reusable (any service can call it)
- Each class has one clear job

**Hints for `app/repositories/auth_repo.py`:**
- Create the file: `app/repositories/auth_repo.py`
- Follow the same pattern as `BookRepo` — take a `Session` in `__init__`
- Implement these methods:
  - `get_by_username(username: str) -> Optional[Account]` — `db.query(Account).filter(...).first()`
  - `get_by_id(user_id: int) -> Optional[Account]` — `db.query(Account).get(user_id)`
  - `create(account: Account) -> Account` — `db.add(account); db.commit(); db.refresh(account); return account`
  - `list_all(role: Optional[RoleEnum] = None) -> list[Account]` — if `role` is provided, filter by it; otherwise return all
  - `has_admin() -> bool` — check if any account with `role == RoleEnum.admin` exists

**Verify:**
```bash
cd backend
python -c "from app.repositories.auth_repo import AuthRepo; print('OK')"
```

- [ ] Create `app/repositories/auth_repo.py`
- [ ] Verify no import errors
- [ ] Commit: `git commit -m "feat: add AuthRepo for database queries"`

---

## Task 10: Update `AuthService`

**Why:** The service layer is where business logic lives. Now that the model has changed, the service needs to:
1. Auto-generate 6-digit passwords for new student accounts
2. Validate credentials against role-specific rules (self-change for students, password strength for teachers/admins)
3. Create users with a specified role
4. Work with `account.role` (a single enum) instead of `account.roles` (a list)
5. Use `AuthRepo` for all database operations instead of direct `db.query()`

**Concept — Role-aware credential validation:**
The validation logic depends on the **context** (creation vs self-change):

```
On account creation:
  if role is student  → auto-generate random 6-digit number (e.g. "482719")
  if role is teacher  → password length must be 8-50
  if role is admin    → password length must be 8-50  ← same as teacher

On self-change (change-password endpoint):
  if role is student  → password length must be 4-50 (relaxed for kids)
  if role is teacher  → password length must be 8-50
  if role is admin    → password length must be 8-50  ← same as teacher

On reset by teacher/admin:
  if role is student  → auto-generate new random 6-digit number
  if role is teacher  → use the password provided in the request (min 8 chars)
  if role is admin    → use the password provided in the request (min 8 chars)
```

This logic belongs in the service, not the router and not the schema (because it depends on two fields together — `role` + `password` — and the context of the operation).

**Hints for `app/services/auth_service.py`:**
- Add a helper: `generate_student_password() -> str` — returns a random 6-digit string. Use Python's `random.randint(100000, 999999)` and convert to string with `str()`.
- Add a static method: `validate_credentials(role: RoleEnum, password: str, context: str = "create") -> None` — the `context` parameter is either `"create"`, `"self_change"`, or `"reset"`. Raises `ValueError` with a descriptive message if the credential doesn't meet the rule.
  - For `context="create"` and `role=student`: skip validation (password is auto-generated)
  - For `context="self_change"` and `role=student`: min 4 chars
  - For `context="create"` and `role=teacher`: min 8 chars
  - For `context="create"` and `role=admin`: min 8 chars
  - For `context="self_change"` and `role=teacher/admin`: min 8 chars
  - For `context="reset"`: skip validation (student gets auto-generated, teacher/admin uses provided password)
- Update `create_user` to accept `db: Session` and `account_data: AccountCreate`. If `role == RoleEnum.student`, call `generate_student_password()` to get the password, hash it, and return the raw password alongside the account. For teacher/admin, use the password from the request and validate it. Use `AuthRepo(db)` for the DB operations.
- Update `authenticate_user` — use `AuthRepo(db).get_by_username()` instead of direct query
- Update `create_token_for_user` — the token payload should have `"role": account.role.value` (a single string) instead of `"roles": [list]`
- Remove `reset_password`'s direct DB query — use `AuthRepo(db).get_by_username()` to stay DRY
- Remove anything that references `recovery_code_hash`

**Imports you will need:**
```python
import random
from app.models import RoleEnum
from app.repositories.auth_repo import AuthRepo
```

**Verify:**
```bash
cd backend
python -c "
from app.services.auth_service import AuthService
from app.models import RoleEnum

# Creation context - student gets auto-generated password
pw = AuthService.generate_student_password()
print(f'Auto-generated student password: {pw}')
assert len(pw) == 6 and pw.isdigit()

# Creation context - teacher and admin password validation
AuthService.validate_credentials(RoleEnum.teacher, 'password1', 'create')
AuthService.validate_credentials(RoleEnum.admin, 'password1', 'create')
print('valid credentials OK')

# Self-change context - student can use short password
AuthService.validate_credentials(RoleEnum.student, 'cat', 'self_change')  # should raise (too short)
try:
    AuthService.validate_credentials(RoleEnum.student, 'cats', 'self_change')
    print('student self-change with 4 chars OK')
except ValueError as e:
    print(f'ERROR: should have accepted: {e}')

# Self-change context - student too short should raise
try:
    AuthService.validate_credentials(RoleEnum.student, 'abc', 'self_change')
    print('ERROR: should have raised')
except ValueError as e:
    print(f'Correctly rejected short password: {e}')
"
```

- [ ] Update `app/services/auth_service.py`
- [ ] Verify with the REPL snippet
- [ ] Commit: `git commit -m "refactor: update AuthService for single-role model with AuthRepo"`

---

## Task 11: Simplify `RoleChecker` in `dependencies/auth.py`

**Why:** With a single `role` attribute instead of a `roles` list, `RoleChecker` becomes dramatically simpler. Understanding FastAPI's `Depends()` system is important — it's how you inject shared logic (like "get the current user") into route handlers without repeating yourself.

**Concept — FastAPI dependency injection:**
```python
# Depends() tells FastAPI: "before calling this route,
# run this function and inject its return value here"
@router.get("/protected")
def protected_route(current_user: Account = Depends(get_current_user)):
    return {"user": current_user.username}

# RoleChecker is a class that acts as a dependency
# __call__ makes an instance of the class callable
class RoleChecker:
    def __init__(self, allowed_roles: list[RoleEnum]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: Account = Depends(get_current_user)) -> Account:
        # current_user is injected by get_current_user
        if current_user.role not in self.allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

# Usage in a router:
@router.post("/admin-only")
def admin_route(user: Account = Depends(RoleChecker([RoleEnum.admin]))):
    ...
```

**Hints for `app/dependencies/auth.py`:**
- Update `get_current_user` — when decoding the JWT, extract `role` (single string) instead of `roles` (list). Use `RoleEnum(payload.get("role"))` to convert back to the enum.
- Rewrite `RoleChecker.__call__` — one line: check if `current_user.role` is in `self.allowed_roles`
- Update the type annotation on `allowed_roles` from `list[str]` to `list[RoleEnum]`
- Remove the `for` loops — no more iteration needed

**Verify:**
The dependency can't be tested in isolation easily, but check for import errors:
```bash
cd backend
python -c "from app.dependencies.auth import get_current_user, RoleChecker; print('OK')"
```

- [ ] Update `app/dependencies/auth.py`
- [ ] Verify no import errors
- [ ] Commit: `git commit -m "refactor: simplify RoleChecker for single-role model"`

---

## Task 12: Rewrite `config.py` (zero-config, auto-generated secrets)

**Why:** For headless SBC deployment, you don't want teachers managing `.env` files. Instead:
- `SECRET_KEY` is **auto-generated on first boot** and persisted to disk — never changes across restarts
- `DATABASE_URL` defaults to SQLite — works out of the box, PostgreSQL-ready via env var if needed later
- No `.env` file required — `docker-compose.yml` has everything visible, no secrets baked into the image

This means: `docker compose up -d` and it just works. Zero config.

**Concept — Auto-generated persistent secret:**
```python
import secrets
from pathlib import Path

SECRET_FILE = Path("/app/data/.secret")

def get_secret_key() -> str:
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()
    key = secrets.token_urlsafe(32)
    SECRET_FILE.write_text(key)
    return key
```

The key is generated once, saved to disk, and read on every startup. If the data folder is wiped, a new key is generated (which invalidates old JWT tokens — acceptable for a factory reset).

**Hints for `app/config.py`:**
- **Remove** `env_file=".env"` from `model_config` — no `.env` file needed
- **Remove** hardcoded `SECRET_KEY` — use `get_secret_key()` as the default
- **Keep** `DATABASE_URL` with a sensible default: `sqlite:///./data/jirani_library.db`
- **Add** `DATA_DIR: Path = BASE_DIR / "data"` — shared location for `.secret`, `.credentials`, and the SQLite DB
- **Add** `ACCESS_TOKEN_EXPIRE_MINUTES: int = 480` (8 hours)
- **Keep** `UPLOAD_DIR`, `COVER_DIR`, `MAX_UPLOAD_SIZE` — unchanged
- **Remove** all `ADMIN_*` env vars — replaced by `/setup` endpoint
- **Add** `ALGORITHM: str = "HS256"` — unchanged
- Override `SECRET_KEY` in `__init__` if it's empty:
  ```python
  def __init__(self, **kwargs):
      super().__init__(**kwargs)
      if not self.SECRET_KEY:
          self.SECRET_KEY = get_secret_key()
  ```

**Verify:**
```bash
cd backend
# Should work with no env vars at all
python -c "from app.config import settings; print(settings.SECRET_KEY[:8] + '...')"
# → Some random string (auto-generated)

# Run again — should return the SAME key
python -c "from app.config import settings; print(settings.SECRET_KEY[:8] + '...')"
# → Same string (persisted to disk)
```

- [ ] Rewrite `app/config.py`
- [ ] Verify: auto-generates SECRET_KEY, persists across runs
- [ ] Commit: `git commit -m "config: zero-config with auto-generated persistent SECRET_KEY"`

---

## Task 13: Create `/setup` endpoint (one-time admin credential generation)

**Why:** The SBC runs headless — no screen, no keyboard. The teacher plugs it in, connects their phone to the network, and opens `http://<sbc-ip>/setup` in their browser. The page generates a unique admin password, saves it to disk, and shows it **exactly once**. If they miss it, they need physical access to the device to recover.

This replaces the env-var bootstrap approach entirely. No `ADMIN_USERNAME` or `ADMIN_PASSWORD` env vars needed.

**Concept — One-time credential generation:**
```
First visit to /setup:
  1. Check if credentials file exists → no
  2. Generate random password (secrets.token_urlsafe(8))
  3. Save to /app/data/.credentials
  4. Create /app/data/.credentials_revealed flag
  5. Show password on HTML page

Second visit to /setup:
  1. Check .credentials_revealed flag → exists
  2. Return 403 "Already configured"
```

**Hints for `app/api/setup_router.py`:**
- Create the file: `app/api/setup_router.py`
- Use `secrets.token_urlsafe(8)` for the password — cryptographically secure, URL-safe
- Store credentials in a JSON file: `/app/data/.credentials` (or `settings.DATA_DIR / ".credentials"`)
- Use a flag file: `/app/data/.credentials_revealed` — once this exists, never show the password again
- Return an `HTMLResponse` with the credentials displayed clearly
- Add a simple confirmation step: "Are you a teacher? [Yes]" — just a speed bump, not real security
- The endpoint should be `GET /setup` — no auth required (it's the first thing the teacher sees)

**File paths:**
```python
import secrets
import json
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["setup"])

CREDENTIALS_FILE = Path("/app/data/.credentials")
REVEALED_FLAG = Path("/app/data/.credentials_revealed")
```

**Note:** In development, use `settings.BASE_DIR / "data"` instead of hardcoded `/app/data`. The Docker volume mount maps `./data` to `/app/data` in production.

**HTML response example:**
```html
<h1>Jirani Library — Admin Setup</h1>
<p><strong>Save these credentials now. They will not be shown again.</strong></p>
<p>Username: <code>admin</code></p>
<p>Password: <code>xK9mP2qR</code></p>
<hr>
<a href="/docs">Go to API docs</a>
```

**Verify:**
```bash
cd backend
# Start the server
uvicorn app.main:app --reload

# First visit
curl http://localhost:8000/setup
# → HTML with generated password

# Second visit
curl http://localhost:8000/setup
# → 403 "Already configured"
```

- [ ] Create `app/api/setup_router.py`
- [ ] Register the router in `app/main.py`: `app.include_router(setup_router.router)`
- [ ] Verify: first visit shows password, second visit returns 403
- [ ] Commit: `git commit -m "feat: add /setup endpoint for one-time admin credential generation"`

---

## Task 14: Update `main.py`

---

## Task 14: Update `main.py`

**Why:** The lifespan context manager handles startup tasks. With the `/setup` endpoint approach, `main.py` no longer needs to seed an admin — it just needs to ensure the data directory exists and register the setup router.

**Hints for `app/main.py`:**
- In the `lifespan` function, after `Base.metadata.create_all(bind=engine)`:
  - Ensure the data directory exists: `settings.DATA_DIR.mkdir(parents=True, exist_ok=True)`
  - **No admin seeding** — that's handled by `/setup`
- Register the setup router: `app.include_router(setup_router.router)`
- Keep the existing CORS middleware, static file mounting, and other routers

**Add to `config.py` (if not already there):**
```python
DATA_DIR: Path = BASE_DIR / "data"
```

**Verify:**
```bash
cd backend
uvicorn app.main:app --reload
# Should start without errors
# Data directory should be created automatically
```

- [ ] Update `app/main.py` — remove seeding logic, ensure data dir, register setup router
- [ ] Verify app starts cleanly
- [ ] Commit: `git commit -m "refactor: update main.py for /setup endpoint, remove env var seeding"`

---

## Task 15: Add bulk creation schemas

**Why:** Teachers need to create many student accounts at once. A bulk endpoint requires new request/response schemas that describe how many accounts to create, what role they should have, and what usernames to generate. The response must include every generated password so the teacher can distribute them.

**Concept — Pydantic validation constraints:**
```python
from pydantic import Field

# Field() accepts validation constraints
count: int = Field(..., ge=1, le=100)  # required, 1 <= count <= 100
prefix: str = Field(default="student", min_length=1, max_length=20)
```
Pydantic automatically rejects requests that violate these constraints and returns a 422 error with a clear message.

**Hints:**
- Open `app/schemas/account_schema.py`
- Add `password: str | None = None` to `AccountCreate` — it's missing and the service needs it
- Add three new classes at the bottom:
  - `BulkCreateRequest` — fields: `count` (1-100), `role`, `prefix` (default "student"), `first_name`, `last_name`
  - `BulkCredentialItem` — fields: `username`, `password`, `role` (one item in the response list)
  - `BulkCreateResponse` — fields: `created` (int), `accounts` (list of `BulkCredentialItem`)
- Then open `app/schemas/__init__.py` and add the three new classes to the import and `__all__`

**Verify:**
```bash
cd backend
python -c "from app.schemas import BulkCreateRequest, BulkCreateResponse; print('OK')"
```

- [ ] Add `password: str | None = None` to `AccountCreate`
- [ ] Add `BulkCreateRequest`, `BulkCredentialItem`, `BulkCreateResponse` to `account_schema.py`
- [ ] Export new schemas from `schemas/__init__.py`
- [ ] Verify no import errors
- [ ] Commit: `git commit -m "feat: add bulk creation schemas"`

---

## Task 16: Add `get_next_prefix_number()` to `AuthRepo`

**Why:** Bulk usernames follow a pattern like `student001`, `student002`, etc. To avoid collisions, the service needs to know what number to start from. The repo queries the database for existing usernames matching a prefix and finds the highest number used.

**Concept — String parsing in Python:**
```python
username = "student042"
prefix = "student"
number_str = username.removeprefix(prefix)  # "042"
number = int(number_str)                     # 42
```
The `removeprefix()` method (Python 3.9+) strips the prefix cleanly. Wrap the result in `int()` to get the number.

**Hints:**
- Open `app/repositories/auth_repo.py`
- Add a method `get_next_prefix_number(self, prefix: str) -> int`
- Query: `self.db_session.query(Account).filter(Account.username.like(f"{prefix}%")).all()`
- For each account, strip the prefix from `username`, parse the remaining digits with `int()`
- Return `max(numbers) + 1` if any matches exist, otherwise return `1`
- Handle edge cases: usernames that match the prefix but have no number after them (skip those)

**Verify:**
```bash
cd backend
python -c "from app.repositories import AuthRepo; print('OK')"
```

- [ ] Add `get_next_prefix_number()` to `AuthRepo`
- [ ] Verify no import errors
- [ ] Commit: `git commit -m "feat: add get_next_prefix_number to AuthRepo"`

---

## Task 17: Add `bulk_create_users()` to `AuthService`

**Why:** The service orchestrates bulk account creation: validate the request (no admin role), generate usernames sequentially, generate role-appropriate passwords, create each account in the database, and collect all credentials for the response.

**Concept — Returning multiple values from a method:**
```python
def create_user(self, metadata: AccountCreate) -> tuple[Account, str]:
    # ... create the account ...
    return new_account, raw_password  # tuple unpacking
```
The caller unpacks: `account, password = service.create_user(data)`. This is Python's idiomatic way to return multiple related values.

**Hints:**
- Open `app/services/auth_service.py`
- Add `bulk_create_users(self, bulk_data: BulkCreateRequest) -> BulkCreateResponse`
- Step 1: Reject admin role — `if bulk_data.role == RoleEnum.admin: raise ValueError(...)`
- Step 2: Get starting number — `number = self.auth_repo.get_next_prefix_number(bulk_data.prefix)`
- Step 3: Loop `bulk_data.count` times:
  - Generate username: `f"{bulk_data.prefix}{number:03d}"`
  - Check if username already exists (skip if so, increment number, continue)
  - Generate password: `generate_student_password()` or `generate_teacher_password()` based on role
  - Create `Account` with username, hashed password, role, first_name, last_name
  - Add to session, commit, refresh
  - Append `{username, password, role}` to a credentials list
  - Increment number
- Step 4: Return `BulkCreateResponse(created=len(credentials), accounts=credentials)`
- Also modify `create_user()` to return `tuple[Account, str]` instead of just `Account`
- Also modify `reset_student_password()` to return `tuple[Account, str]`

**Verify:**
```bash
cd backend
python -c "from app.services import AuthService; print('OK')"
```

- [ ] Add `bulk_create_users()` to `AuthService`
- [ ] Change `create_user()` return type to `tuple[Account, str]`
- [ ] Change `reset_student_password()` return type to `tuple[Account, str]`
- [ ] Verify no import errors
- [ ] Commit: `git commit -m "feat: add bulk_create_users to AuthService"`

---

## Task 18: Redesign `auth_router.py`

**Why:** This is the router rewrite — adding new endpoints, fixing bugs, and removing security holes. Each endpoint should do one thing: validate input, call the service, return the response. Your current router has 3 endpoints (`/token`, `/reset-student-password`, `/change-password`). You'll expand to 7.

**Concept — FastAPI endpoint pattern:**
```python
@router.post("/endpoint", response_model=SomeResponse, status_code=status.HTTP_201_CREATED)
async def some_endpoint(
    data: SomeRequest,                          # request body
    auth_service: AuthService = Depends(get_auth_service),  # service layer
    current_user: Account = Depends(RoleChecker([RoleEnum.admin]))  # auth guard
):
    # 1. Validate (role restrictions, business rules)
    # 2. Call service (may raise ValueError)
    # 3. Return response
```
The pattern is consistent: guard → validate → call service → return. If the service raises `ValueError`, catch it and convert to `HTTPException(400, ...)`.

**Hints for each endpoint:**

### `POST /auth/token` (login) — keep as-is
No changes needed. It already works correctly.

### `POST /auth/users` (create single user — new)
- Protect with `RoleChecker([RoleEnum.admin, RoleEnum.teacher])`
- If teacher tries to create non-student → 403
- Call `auth_service.create_user(account_data)` — unpack the tuple: `account, raw_password = ...`
- Catch `ValueError` → `HTTPException(400, ...)`
- Return `CreateUserResponse.model_validate({...**, "credentials": raw_password})`

### `POST /auth/users/bulk` (mass create — new)
- Protect with `RoleChecker([RoleEnum.admin, RoleEnum.teacher])`
- If role is admin → 400 "Cannot create admin accounts via bulk endpoint"
- If teacher tries to create non-student → 403
- Call `auth_service.bulk_create_users(bulk_data)` — returns `BulkCreateResponse` directly
- Return the response

### `GET /auth/users` (list users — new)
- Protect with `RoleChecker([RoleEnum.admin, RoleEnum.teacher])`
- If teacher → `auth_service.auth_repo.list_all(role=RoleEnum.student)`
- If admin → `auth_service.auth_repo.list_all()`
- Return `list[AccountRead]`

### `GET /auth/me` (current user — new)
- Protect with `get_current_user` (any authenticated user)
- Return `AccountRead.model_validate(current_user)`

### `POST /auth/reset-password` (rename from `/reset-student-password`)
- Rename the route to `/reset-password`
- Protect with `RoleChecker([RoleEnum.admin, RoleEnum.teacher])`
- Look up target user by `account_id` → 404 if not found
- If teacher and target is not student → 403
- Call `auth_service.reset_student_password(account_id)` — unpack tuple: `account, new_password = ...`
- Return `{"message": f"Password reset for {account.username}", "new_password": new_password}`

### `POST /auth/change-password` (fix)
- Change protection to `get_current_user` (any authenticated user, not just admin/teacher)
- Verify old password → 400 if incorrect
- Call `AuthService.validate_credentials(current_user.role, new_password, context="self_change")` — catch `ValueError` → 400
- Call `auth_service.change_password(current_user.username, new_password)`
- Return success message

**Verify:**
Start the server and test each endpoint via Swagger UI (`http://localhost:8000/docs`):
1. `GET /setup` → get admin credentials
2. `POST /auth/token` → login as admin, get token
3. `POST /auth/users` → create a teacher account → response includes raw password
4. `POST /auth/users` as teacher → try to create admin → should get 403
5. `POST /auth/users/bulk` → `{"count": 5, "role": "student", "prefix": "classA"}` → creates `classA001` through `classA005`
6. `GET /auth/users` as teacher → should only see students
7. `GET /auth/me` as student → should return student profile
8. `POST /auth/token` as student → login with auto-generated PIN
9. `POST /auth/change-password` as student → change to 4+ digit PIN
10. `POST /auth/reset-password` as teacher → reset student PIN → returns new 6-digit PIN

- [ ] Rewrite `auth_router.py` with all 7 endpoints
- [ ] Test each endpoint via Swagger UI
- [ ] Commit: `git commit -m "feat: redesign auth router with bulk creation and security fixes"`

---

## Task 19: Delete `.env.example` (no longer needed)

**Why:** The app is zero-config — no `.env` file required. All secrets are auto-generated. The `.env.example` file is misleading because it implies the user needs to configure something.

- [ ] Delete `.env.example`
- [ ] Commit: `git commit -m "chore: remove .env.example — app is zero-config"`

---

## Task 20: Delete old scripts

**Why:** The old scripts create users by directly manipulating the DB, bypassing all validation. The new `POST /auth/users` endpoint replaces them. Keeping dead scripts causes confusion.

- [ ] Delete `app/scripts/create_admin.py`
- [ ] Delete `app/scripts/create_test_users.py`
- [ ] Delete `app/scripts/test_reset_password.py` (also outdated)
- [ ] Commit: `git commit -m "chore: remove outdated user creation scripts"`

---

## Task 21: Write tests

**Why:** Tests prove the system works as designed and protect you from breaking it when you make future changes. FastAPI has a built-in test client (`TestClient`) that lets you make HTTP requests to your app without running a real server.

**Concept — FastAPI TestClient:**
```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_login_success():
    response = client.post("/auth/token", json={"username": "admin", "password": "strongpassword123"})
    assert response.status_code == 200
    assert "access_token" in response.json()
```

**Concept — In-memory SQLite for tests:**
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
Base.metadata.create_all(bind=engine)
```
This replaces the real database with a fresh in-memory one for each test run. Tests are fast and don't touch your real data.

**Hints for `app/tests/test_auth.py`:**
- Create a `conftest.py` in `app/tests/` with the in-memory DB setup
- Write tests for at least these cases:
  1. `test_setup_first_visit_generates_credentials` → 200, password in response
  2. `test_setup_second_visit_returns_403` → 403
  3. `test_login_wrong_password` → 401
  4. `test_create_student_as_admin` → 201, auto-generated 6-digit credential in response
  5. `test_create_admin_as_teacher` → 403
  6. `test_bulk_create_students` → 200, returns list of usernames + passwords
  7. `test_bulk_create_as_teacher_only_students` → 200 for students, 403 for teachers
  8. `test_bulk_create_no_admin` → 400 when requesting admin role
  9. `test_reset_password_as_teacher` → 200, new 6-digit credential in response
  10. `test_reset_teacher_password_as_teacher` → 403 (teacher can't reset other teachers)
  11. `test_get_users_as_teacher_only_sees_students` → 200, all returned roles are `student`
  12. `test_student_can_change_own_password` → 200, with min 4 char password
  13. `test_student_change_password_too_short` → 422 (password < 4 chars)

**Run tests:**
```bash
cd backend
pytest app/tests/test_auth.py -v
```

- [ ] Create `app/tests/conftest.py` with in-memory DB fixture
- [ ] Create `app/tests/test_auth.py` with test cases
- [ ] Run tests and make them all pass
- [ ] Commit: `git commit -m "test: add auth endpoint tests"`

---

## Final verification

Run the full quality check suite from `AGENTS.md`:

```bash
cd backend
ruff format .
ruff check . --fix
mypy . --strict
pytest -v -k "auth"
```

Fix any issues that come up before considering this done.

- [ ] Format passes
- [ ] Lint passes (or all remaining issues are explained)
- [ ] Type check passes
- [ ] Tests pass
- [ ] Commit: `git commit -m "chore: final lint and type check pass for auth redesign"`

---

## What you learned

After completing this plan, you will have hands-on experience with:

- **Python Enums** — fixed value sets with type safety
- **SQLAlchemy 2.0** — `Mapped[T]`, `mapped_column()`, mixins
- **Pydantic v2** — `ConfigDict`, `Annotated` types, schema layering
- **FastAPI dependency injection** — `Depends()`, `RoleChecker` pattern
- **JWT tokens** — what goes in the payload, how it's verified
- **12-factor app config** — secrets from env vars, not code
- **bcrypt** — why you hash passwords and never store them plain
- **API security basics** — why open endpoints are dangerous, RBAC patterns
- **Testing FastAPI** — `TestClient`, in-memory DB for test isolation
- **Auto-generated credentials** — when to let the system generate passwords vs requiring user input
- **Context-aware validation** — different rules for creation, self-change, and admin reset
