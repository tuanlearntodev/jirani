---
description: Tick a completed plan task's checkbox and include it in the commit
---

Mark a plan task complete.

The argument is a task reference such as `S1`, `A2`, or `Task 0` from a file under `docs/superpowers/plans/`. `$ARGUMENTS`

Do this:

1. Find the matching task. List the plan tree and grep for the task id:
   ```
   grep -rn "\*\*Step\|### Task\|## Task" docs/superpowers/plans/ | grep -i "$ARGUMENTS"
   ```
2. Confirm with me which exact box it is before editing (a bare number is ambiguous across two plans).
3. Flip its `- [ ]` to `- [x]` in the plan file. `docs/**` is writable.
4. If there are uncommitted code changes that this task produced, stage the plan file **with** them and commit together. If nothing is staged, commit the tick alone as `chore: tick <task>`.
5. If you cannot find the task, or the box is already ticked, say so and stop — do not guess.

Per AGENTS.md "Tick the plan box in the same commit", prefer folding the tick into the code commit when one exists.
