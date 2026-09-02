---
description: Run the Definition of Done gate (ruff, mypy, pytest) and report pass/fail
agent: verifier
---

Run the full Definition of Done gate for this repository.

Files changed in the working tree:

!`git diff --name-only; git diff --cached --name-only; git status --porcelain | grep '^??' | cut -c4-`

Scope `mypy --strict` to the changed Python files under `backend/` shown above. If that list is empty, say so and run only format, lint, and the full test suite.

Report using your standard Definition of Done output format.
