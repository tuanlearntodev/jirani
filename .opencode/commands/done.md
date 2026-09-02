---
description: Gate a plan task — run invariant audit + DoD verify, tick the box only if both pass
---

Run the completion gate for the task referenced by `$ARGUMENTS` (e.g. `Task 1`, `7`, `S1`), then tick it only if both subagents pass. If `$ARGUMENTS` is empty, ask the user which task before doing anything.

## 1. Resolve the task box

```
grep -rn "### Task\|## Task" docs/superpowers/plans/ | grep -i "$ARGUMENTS"
```

- Exactly one match → proceed.
- Zero matches, multiple matches, or the box is already ticked → say so and stop. Do not guess. (A bare number can be ambiguous across plan files — the grep tells you.)

## 2. Collect the review inputs (run once, reuse for both dispatches)

!`git status --short`
!`git diff`
!`git diff --cached`
!`git diff --name-only; git diff --cached --name-only; git status --porcelain | grep '^??' | cut -c4-`

## 3. Dispatch both subagents in parallel (one message, two task calls)

- **`invariant-auditor`** — self-contained prompt: "Audit the current uncommitted change against the six binding invariants in AGENTS.md. Changed files: <status output>. Diff: <git diff + git diff --cached outputs>. Report using your standard invariant audit output format."
- **`verifier`** — self-contained prompt: "Run the full Definition of Done gate for this repository. Changed files: <name-only output>. Scope mypy --strict to the changed Python files under backend/; if empty, run format/lint/full suite only. Report using your standard DoD output format."

Both agents are read-only. Fix nothing during this step. Do not commit whatever they say.

## 4. Gate on the reports

- **Both PASS** (audit: no NEW violations outside the known debt table; verifier: all DoD commands pass including the TDD red-evidence gate) → step 5.
- **Either is FAIL / VIOLATION / NOT DONE** → **do not tick.** Paste the failing output back to the user verbatim and stop. Do not loop more than 3 total attempts; on the 3rd failure, stop and ask for direction (AGENTS.md escalation).

## 5. Tick + commit

- Flip the task's `- [ ]` to `- [x]` in the plan file under `docs/superpowers/plans/` (`docs/**` is writable).
- Per AGENTS.md "Tick the plan box in the same commit": if the task produced uncommitted code changes, stage the plan file with them and commit together. If nothing is staged, commit the tick alone as `chore: tick <task>`.

Report: which task, both agent verdicts (one line each), whether the box was ticked, and the commit hash if one was made.
