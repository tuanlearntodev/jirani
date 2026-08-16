---
description: Audit the current diff against the six binding invariants in AGENTS.md
agent: invariant-auditor
---

Audit the current uncommitted change against the six binding invariants.

Changed files:

!`git status --short`

The diff:

!`git diff`

Staged changes, if any:

!`git diff --cached`

If `$ARGUMENTS` is non-empty, treat it as a narrower scope (a path, or an invariant number) and audit only that.

Report using your standard invariant audit output format.
