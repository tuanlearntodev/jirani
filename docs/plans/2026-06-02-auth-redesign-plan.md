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
| `app/models/enums.py` | **Create** | `RoleEnum` lives here |
| `app/models/base.py` | **Create** | `TimestampMixin` lives here |
| `app/models/account.py` | **Rewrite** | SQLAlchemy 2.0 style, add `role`, timestamps |
| `app/models/role.py` | **Delete** | Replaced by `RoleEnum` |
| `app/models/account_role.py` | **Delete** | Merged into `accounts` table |
| `app/models/__init__.py` | **Update** | Remove old imports |
| `app/schemas/auth_schema.py` | **Rewrite** | Pydantic v2 style, Annotated types |
| `app/schemas/account_schema.py` | **Populate** | Layered schemas: Base → Create → Read |
| `app/services/auth_service.py` | **Update** | Role-aware credential validation, new user creation |
| `app/dependencies/auth.py` | **Update** | Simplify `RoleChecker` for single-role model |
| `app/config.py` | **Update** | Add admin bootstrap env vars |
| `app/main.py` | **Update** | Startup admin seeding |
| `app/api/auth_router.py` | **Rewrite** | Remove holes, add new endpoints |
| `app/scripts/create_admin.py` | **Delete** | Replaced by env var bootstrap |
| `app/scripts/create_test_users.py` | **Delete** | Replaced by `POST /auth/users` |
| `.env.example` | **Update** | Document new env vars |
| `app/tests/test_auth.py` | **Create** | Tests for new auth endpoints |

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

## Task 9: Update `AuthService`

**Why:** The service layer is where business logic lives. Now that the model has changed, the service needs to:
1. Auto-generate 6-digit passwords for new student accounts
2. Validate credentials against role-specific rules (self-change for students, password strength for teachers/admins)
3. Create users with a specified role
4. Work with `account.role` (a single enum) instead of `account.roles` (a list)

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
- Add a static method: `validate_credential(role: RoleEnum, password: str, context: str = "create") -> None` — the `context` parameter is either `"create"`, `"self_change"`, or `"reset"`. Raises `ValueError` with a descriptive message if the credential doesn't meet the rule.
  - For `context="create"` and `role=student`: skip validation (password is auto-generated)
  - For `context="self_change"` and `role=student`: min 4 chars
  - For `context="create"` and `role=teacher`: min 8 chars
  - For `context="create"` and `role=admin`: min 12 chars
  - etc.
- Update `create_user` to accept `role: RoleEnum` as a parameter. If `role == RoleEnum.student`, call `generate_student_password()` to get the password, hash it, and return the raw password alongside the account. For teacher/admin, use the password from the request and validate it.
- Update `authenticate_user` — the query no longer needs to worry about roles; it just returns the account if username and password match and `is_active` is True
- Update `create_token_for_user` — the token payload should have `"role": account.role.value` (a single string) instead of `"roles": [list]`
- Remove `reset_password`'s direct DB query — it already takes `username`, so just use `get_user_by_username` to stay DRY
- Remove anything that references `recovery_code_hash`

**Imports you will need:**
```python
import random
from app.models.enums import RoleEnum
```

**Verify:**
```bash
cd backend
python -c "
from app.services.auth_service import AuthService
from app.models.enums import RoleEnum

# Creation context - student gets auto-generated password
pw = AuthService.generate_student_password()
print(f'Auto-generated student password: {pw}')
assert len(pw) == 6 and pw.isdigit()

# Creation context - teacher and admin password validation
AuthService.validate_credential(RoleEnum.teacher, 'password1', 'create')
AuthService.validate_credential(RoleEnum.admin, 'password1', 'create')
print('valid credentials OK')

# Self-change context - student can use short password
AuthService.validate_credential(RoleEnum.student, 'cat', 'self_change')  # should raise (too short)
try:
    AuthService.validate_credential(RoleEnum.student, 'cats', 'self_change')
    print('student self-change with 4 chars OK')
except ValueError as e:
    print(f'ERROR: should have accepted: {e}')

# Self-change context - student too short should raise
try:
    AuthService.validate_credential(RoleEnum.student, 'abc', 'self_change')
    print('ERROR: should have raised')
except ValueError as e:
    print(f'Correctly rejected short password: {e}')
"
```

- [ ] Update `app/services/auth_service.py`
- [ ] Verify with the REPL snippet
- [ ] Commit: `git commit -m "refactor: update AuthService for single-role model"`

---

## Task 10: Simplify `RoleChecker` in `dependencies/auth.py`

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

## Task 11: Add admin bootstrap env vars to `config.py`

**Why:** Hardcoding credentials in scripts is a security risk. The **12-factor app** methodology says configuration (secrets, URLs, usernames) should come from environment variables — that way the same code runs in dev with test credentials and in production with real ones, and secrets never end up in git.

**Concept — Optional env vars with Pydantic Settings:**
```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    ADMIN_USERNAME: Optional[str] = None  # None means "not set"
    ADMIN_PASSWORD: Optional[str] = None
```

When these are `None`, the bootstrap logic in `main.py` will simply skip seeding.

**Hints for `app/config.py`:**
- Add four new optional fields to the `Settings` class:
  - `ADMIN_USERNAME: Optional[str] = None`
  - `ADMIN_PASSWORD: Optional[str] = None`
  - `ADMIN_FIRST_NAME: str = "Admin"` (has a default)
  - `ADMIN_LAST_NAME: str = "User"` (has a default)
- Import `Optional` from `typing` (or use `str | None` in Python 3.10+ style)
- Also update `ACCESS_TOKEN_EXPIRE_MINUTES` to `480` (8 hours = 480 minutes) — it's currently `30`

**Verify:**
```bash
cd backend
python -c "from app.config import settings; print(settings.ADMIN_USERNAME, settings.ACCESS_TOKEN_EXPIRE_MINUTES)"
# Should print: None 480
```

- [ ] Update `app/config.py`
- [ ] Verify output above
- [ ] Commit: `git commit -m "config: add admin bootstrap env vars and 8h token expiry"`

---

## Task 12: Add startup admin seeding to `main.py`

**Why:** The lifespan context manager in FastAPI is the right place for startup logic — things that must run once when the app boots. Seeding the first admin here means you don't need a separate script, and Docker deployments just need the right env vars.

**Concept — FastAPI lifespan:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP: runs once when app starts ---
    do_startup_things()
    yield
    # --- SHUTDOWN: runs once when app stops ---
    do_cleanup_things()

app = FastAPI(lifespan=lifespan)
```

**Hints for `app/main.py`:**
- Inside the `lifespan` function, after `Base.metadata.create_all(bind=engine)`, add a call to a helper function `seed_admin_if_needed()`
- Write `seed_admin_if_needed()` as a standalone function in `main.py` (or a `startup.py` file if you prefer):
  - Get a DB session using `SessionLocal()` (not `get_db()` — that's for request contexts)
  - Check if `settings.ADMIN_USERNAME` and `settings.ADMIN_PASSWORD` are both set — if not, return early
  - Check if any account with `role == RoleEnum.admin` already exists in the DB — if yes, return early (don't overwrite)
  - If no admin exists: call `AuthService.validate_credential(RoleEnum.admin, settings.ADMIN_PASSWORD)` — raise a clear error if the password is too weak
  - Call `AuthService.create_user(db, ...)` with `role=RoleEnum.admin`
  - Close the DB session in a `finally` block
  - Print a success message to the console

**Verify:**
- Set env vars and start the server:
  ```bash
  ADMIN_USERNAME=admin ADMIN_PASSWORD=strongpassword123 uvicorn app.main:app --reload
  ```
- Check the console — you should see a message like "Admin account seeded"
- Open Swagger at `http://localhost:8000/docs`, call `POST /auth/token` with those credentials — you should get a token back
- Start the server again — the seeding should NOT run a second time (the admin already exists)

- [ ] Add `seed_admin_if_needed()` to `main.py`
- [ ] Add call to it in the lifespan startup block
- [ ] Verify seeding works on first boot, skips on second boot
- [ ] Commit: `git commit -m "feat: seed first admin from env vars on startup"`

---

## Task 13: Redesign `auth_router.py`

**Why:** This is the biggest change — adding new endpoints, fixing bugs, and deleting the security holes. Each endpoint should do one thing: validate input, call the service, return the response.

**Bug to fix — `change-password`:**
The current endpoint has `current_user: Account = Depends(RoleChecker(["admin"]))`. This is wrong — it means only admins can change their own password. The fix: use `RoleChecker([RoleEnum.admin, RoleEnum.teacher])`.

**Security holes to remove:**
Delete the entire `seed_roles` and `make_admin` endpoint functions. They are gone.

**Hints for each new/changed endpoint:**

### `POST /auth/token` (login)
- Functionally unchanged, but update the response model to `TokenResponse` from `auth_schema.py`
- `Token.roles` → `TokenResponse.role` (single string now)

### `POST /auth/users` (create user — new)
- Protect with `Depends(RoleChecker([RoleEnum.admin, RoleEnum.teacher]))`
- Parse the request body as `AccountCreate` from `account_schema.py`
- Add a **role restriction check**: if `current_user.role == RoleEnum.teacher` and the requested `account_data.role != RoleEnum.student`, raise `HTTPException(status_code=403, detail="Teachers can only create student accounts")`
- Call `AuthService.create_user(db, account_data)` — it may raise `ValueError` (weak credential, duplicate username) — catch that and raise `HTTPException(400, ...)`
- Return `CreateUserResponse` — include the raw `credential` (the plain text password before hashing) so the teacher can write it down and hand it to the student
- **Important:** For student accounts, the password is auto-generated by the service. For teacher/admin accounts, the password comes from the request body. The service returns the raw credential in both cases.

### `GET /auth/users` (list users — new)
- Protect with `Depends(RoleChecker([RoleEnum.admin, RoleEnum.teacher]))`
- Query `db.query(Account)`
- If `current_user.role == RoleEnum.teacher`, filter to `role == RoleEnum.student` only
- Return a `list[AccountRead]`

### `GET /auth/me` (current user — new)
- Protect with `Depends(get_current_user)` (any authenticated user)
- Return `AccountRead.model_validate(current_user)`

### `POST /auth/reset-password` (fix)
- Update protection to `Depends(RoleChecker([RoleEnum.admin, RoleEnum.teacher]))`
- Add restriction: if `current_user.role == RoleEnum.teacher`:
  - Look up the target user by username
  - If target user's role is not `student`, raise `HTTPException(403, "Teachers can only reset student PINs")`
- For **student** accounts: auto-generate a new 6-digit password via `AuthService.generate_student_password()` and return it in the response
- For **teacher/admin** accounts: use the `new_password` from the request body

### `POST /auth/change-password` (fix)
- Fix the protection: `Depends(get_current_user)` — **any authenticated user** can change their own password (not just admin/teacher)
- Remove the `username` field from the request — the user comes from `current_user`
- Verify `old_password` against `current_user.hashed_password`
- Call `AuthService.validate_credential(current_user.role, change_data.new_password, context="self_change")` to enforce role-appropriate strength rules (student: min 4 chars, teacher/admin: 8+)
- Hash and save the new password

**Removed endpoints** — delete these functions entirely:
- `seed_roles`
- `make_admin`
- `signup`
- `verify_recovery_code`
- `admin_exists`

**Verify:**
Start the server and test each endpoint via Swagger UI (`http://localhost:8000/docs`):
1. Login with the seeded admin → get token
2. Use the token to call `POST /auth/users` to create a teacher account
3. Use teacher token to call `POST /auth/users` to create a student account → response includes auto-generated 6-digit password
4. Try to create an admin as a teacher → should get 403
5. Call `GET /auth/me` with the student token → should return student profile
6. Call `GET /auth/users` as teacher → should only see students
7. Login as the student with the auto-generated password → should work
8. As the student, call `POST /auth/change-password` with a new 4+ char password → should work
9. As the teacher, call `POST /auth/reset-password` for the student → should return a new 6-digit password

- [ ] Rewrite `app/api/auth_router.py`
- [ ] Test each endpoint manually via Swagger
- [ ] Commit: `git commit -m "feat: redesign auth router with new endpoints and security fixes"`

---

## Task 14: Update `.env.example`

**Why:** `.env.example` is documentation for anyone who clones this project. It tells them what environment variables the app needs, without exposing real values.

- [ ] Open `.env.example`
- [ ] Add the new variables with placeholder values and a comment explaining each:
  ```
  # Admin bootstrap — set these to seed the first admin on startup
  # ADMIN_PASSWORD must be at least 8 characters
  ADMIN_USERNAME=admin
  ADMIN_PASSWORD=changeme8
  ADMIN_FIRST_NAME=Admin
  ADMIN_LAST_NAME=User

  # Token expiry (minutes) — 480 = 8 hours
  ACCESS_TOKEN_EXPIRE_MINUTES=480
  ```
- [ ] Commit: `git commit -m "docs: update .env.example with new auth env vars"`

---

## Task 15: Delete old scripts

**Why:** The old scripts create users by directly manipulating the DB, bypassing all validation. The new `POST /auth/users` endpoint replaces them. Keeping dead scripts causes confusion.

- [ ] Delete `app/scripts/create_admin.py`
- [ ] Delete `app/scripts/create_test_users.py`
- [ ] Delete `app/scripts/test_reset_password.py` (also outdated)
- [ ] Commit: `git commit -m "chore: remove outdated user creation scripts"`

---

## Task 16: Write tests

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

**Hints for `app/tests/test_auth.py`:**
- Use an **in-memory SQLite** database for tests so tests don't touch your real DB:
  ```python
  # In a conftest.py or at the top of the test file
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
- Write tests for at least these cases:
  1. `test_login_wrong_password` → 401
  2. `test_create_student_as_admin` → 201, auto-generated 6-digit credential in response
  3. `test_create_admin_as_teacher` → 403
  4. `test_reset_student_password_as_teacher` → 200, new 6-digit credential in response
  5. `test_reset_teacher_password_as_teacher` → 403 (teacher can't reset other teachers)
  6. `test_get_users_as_teacher_only_sees_students` → 200, all returned roles are `student`
  7. `test_student_can_change_own_password` → 200, with min 4 char password
  8. `test_student_change_password_too_short` → 422 (password < 4 chars)

**Run tests:**
```bash
cd backend
pytest app/tests/test_auth.py -v
```

- [ ] Create `app/tests/test_auth.py`
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
