---
name: state
description: Manages STATE.md, the project's living status file. Use when the user signals task completion ("verify and commit", "done", "ship it", "we're done", "that's it", "heading out", "goodbye"), says "remind me to do X" / "remember to" / "don't forget to", says "session handoff" / "switching machines" / "new machine" / "handoff", or confirms a commit ("yes", "commit it", "go ahead", "commit please", "push it") after being asked to commit. Updates project state, in-progress work, reminders, decisions, and graveyard on every trigger.
compatibility: opencode
---

## What I do

- Maintain `STATE.md` at the repository root as the single source of truth for project state.
- Refresh it on task completion, reminder creation, or session handoff.
- Sync reminders to the Memory MCP as TODO entities for cross-session recall.

## When to use me

Trigger on any of these signals from the user:

- **Task completion:** "verify and commit", "done", "ship it", "we're done", "that's it", "heading out", "goodbye"
- **Commit confirmation:** "yes", "commit it", "go ahead", "commit please", "push it" — when the user confirms a commit you proposed (you asked "want me to commit?" and they said yes)
- **Reminder:** "remind me to do X", "remember to X", "don't forget to X"
- **Session handoff:** "session handoff", "switching machines", "new machine", "handoff"

## Instructions

### On task completion

1. Run verification commands if not already done (per AGENTS.md: `ruff format .`, `ruff check . --fix`, `mypy . --strict`, `pytest -v -k "<module>"`).
2. Read the current `STATE.md` (or create it if missing using the template below).
3. Update the header: `Last Updated` (current timestamp), `Branch` (`git branch --show-current`), `Uncommitted` (`git status --porcelain` output or "clean").
4. Refresh `## Current State` with 2-3 sentences on what works, what's deployed, current health.
5. Move completed items out of `## In Progress` (mark `[x]` or remove).
6. If decisions were made this task, append to `## Decisions Log` with date, decision, and why.
7. If approaches were tried and failed, append to `## Graveyard` with the attempt and why it failed.
8. Update `## Next Steps` with the immediate next technical steps.
9. Save the file. Do NOT auto-commit unless the user explicitly asked to commit.

### On commit confirmation ("yes", "commit it", "go ahead", etc.)

This is a lighter update than full task completion — the user already decided to commit, just update state to reflect what was committed.

1. Read the current `STATE.md` (create if missing).
2. Update the header: `Last Updated` (current timestamp + new commit sha after commit lands), `Branch`, `Uncommitted`.
3. If the committed work completed an in-progress item, mark it `[x]` or remove from `## In Progress`.
4. If decisions were made, append to `## Decisions Log`.
5. Update `## Next Steps` if the commit unblocks the next task.
6. Save `STATE.md`. Commit it together with the user's requested changes (same commit).

### On "remind me to do X"

1. Append `- [ ] X (priority: low, added: YYYY-MM-DD)` to `## Remind Me (Future)` in STATE.md.
2. Call `memory_create_entities` with:
   - `name`: `"TODO: <short description>"`
   - `entityType`: `"TODO"`
   - `observations`: `[the full reminder text, "priority: low|medium|high", "added: YYYY-MM-DD", "project: <project name>"]`
3. Confirm to the user: "Saved to STATE.md and memory."

### On "session handoff" / "switching machines"

1. Do a full refresh of all sections (as in task completion).
2. Ensure `## Next Steps` is detailed enough for a fresh machine to resume work.
3. Ensure `## Graveyard` captures every failed attempt from this session.
4. Tell the user to commit STATE.md: `git add STATE.md && git commit -m "Update state"`.
5. Remind them: on the new machine, run `git pull && cat STATE.md` to resume.

## STATE.md template

If `STATE.md` does not exist, create it with this structure:

    # Project State — <project name>

    **Last Updated:** YYYY-MM-DD HH:MM (commit <sha>)
    **Branch:** <branch>
    **Uncommitted:** <files or "clean">

    ## Current State
    <2-3 sentences: what works, what's deployed, current health>

    ## In Progress
    - [ ] <active task>

    ## Remind Me (Future)
    - [ ] <future idea> (priority: low/med/high, added: YYYY-MM-DD)

    ## Decisions Log
    - YYYY-MM-DD: <decision> — <why>

    ## Graveyard (Tried & Didn't Work)
    - **Attempt:** <approach> — _Why it failed:_ <reason>

    ## Next Steps
    1. [ ] <immediate next technical step>
    2. [ ] <secondary step>

## Rules

- NEVER delete entries from `## Decisions Log` or `## Graveyard` — they are append-only history.
- `## Remind Me` entries can be removed when completed, but only after the user confirms.
- Always update the `Last Updated` header, even for small changes.
- If STATE.md is not committed, remind the user to commit it so it survives machine switches.
