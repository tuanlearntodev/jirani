# Design: Mass Account Creation for Students/Teachers

## Context

The Jirani Offline Library targets children with low digital literacy. Teachers need to create many student accounts quickly. Currently, `POST /auth/users` creates one account at a time with manual username/password input.

## Problem

Creating 30+ student accounts one-by-one is tedious. Teachers need a faster way to bulk-create accounts with predictable usernames and auto-generated passwords.

## Constraints

- **No admin creation via mass endpoint** — only `student` and `teacher` roles allowed
- **Auto-generated passwords** — all mass-created accounts get random passwords (6-digit PIN for students, URL-safe string for teachers)
- **Predictable usernames** — prefix + sequential number (e.g., `student001`, `student002`)
- **Future: spreadsheet upload** — design should accommodate CSV/Excel upload later
- **Response includes credentials** — teacher needs to see all generated passwords to distribute

## Design

### Endpoint: `POST /auth/users/bulk`

**Request:**
```json
{
  "count": 30,
  "role": "student",
  "prefix": "student",
  "first_name": "Student",
  "last_name": "Account"
}
```

**Fields:**
- `count` (int, 1-100): Number of accounts to create
- `role` (enum: "student" | "teacher"): Role for all accounts
- `prefix` (str, optional, default "student" or "teacher"): Username prefix
- `first_name` (str, optional, default "Student" or "Teacher"): Default first name
- `last_name` (str, optional, default "Account" or "Account"): Default last name

**Response:**
```json
{
  "created": 30,
  "accounts": [
    {"username": "student001", "password": "123456", "role": "student"},
    {"username": "student002", "password": "789012", "role": "student"}
  ]
}
```

**Protection:** `RoleChecker([RoleEnum.admin, RoleEnum.teacher])`
**Restriction:** Teachers can only create student accounts (not teacher accounts)

### Service: `bulk_create_users(count, role, prefix, first_name, last_name)`

1. Validate `count` (1-100)
2. Validate `role` (no admin)
3. If teacher caller and role != student → 403
4. Determine starting number by querying existing accounts with same prefix pattern
5. Loop `count` times:
   - Generate username: `{prefix}{number:03d}`
   - Generate password (role-appropriate)
   - Create account via existing `create_user` logic
   - Collect credentials
6. Return list of usernames + passwords

### Schema: `BulkCreateRequest` and `BulkCreateResponse`

```python
class BulkCreateRequest(BaseModel):
    count: int = Field(..., ge=1, le=100)
    role: RoleEnum
    prefix: str = Field(default="student", min_length=1, max_length=20)
    first_name: str = Field(default="Student", min_length=1, max_length=50)
    last_name: str = Field(default="Account", min_length=1, max_length=50)

class BulkCredentialItem(BaseModel):
    username: str
    password: str
    role: RoleEnum

class BulkCreateResponse(BaseModel):
    created: int
    accounts: list[BulkCredentialItem]
```

### Future: Spreadsheet Upload

Later, add `POST /auth/users/bulk/upload` accepting CSV/Excel with columns: `username`, `first_name`, `last_name`, `role` (optional, defaults to student). Passwords always auto-generated.

## Error Handling

- `count > 100` → 422 validation error
- `role == admin` → 400 "Cannot create admin accounts via bulk endpoint"
- Teacher creating teacher accounts → 403 "Teachers can only create student accounts"
- Username collision → skip and continue, report skipped count in response
