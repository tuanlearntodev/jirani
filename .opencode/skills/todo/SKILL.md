---
name: todo
description: Generates a project briefing showing what's done, what's overdue, and what to work on next. Use when the user types /todo or says "what should I work on" or "give me a briefing" or "what's the status". Reads STATE.md, the refactor plan, git log, and previous briefing to produce a focused daily plan.
compatibility: opencode
---

## What I do

Generate a project briefing that shows:
- What's overdue from the last session
- What's done so far
- What to work on next
- A 30-minute plan for today
- Reminders and blockers

## When to use me

- User types `/todo`
- User says "what should I work on"
- User says "give me a briefing" or "what's the status"
- User starts a session and wants to know where they left off

## Instructions

1. **Read STATE.md** (repo root) — current project state, in-progress tasks, reminders, next steps.

2. **Read the plan** — `docs/plans/2026-07-03-book-refactor-plan.md`. Check which tasks have `[x]` vs `[ ]` to see progress.

3. **Run `git log --oneline -20`** — see recent commits to understand what was recently completed.

4. **Run `git status --short`** — see uncommitted work that might need attention.

5. **Read `todos/morning-briefing.prev.md`** if it exists — compare its "Today's Plan" checklist against what actually happened (git log, STATE.md). Any incomplete items go in the Urgent section.

6. **Generate the briefing** with exactly these sections IN THIS ORDER:

```
# Briefing — <Day of week, Month Day Year>

## Urgent (Overdue from last session)
<Any planned steps that were NOT completed. If nothing is overdue, write "Nothing overdue. Good job.">

## Done So Far
<List of completed tasks based on plan checkboxes + git commits>

## Next Up
<The next incomplete task from the plan. Include task number and title.>

## Today's Plan (30 min)
<Break the next task into 3-5 concrete steps with verify commands. Use checkboxes.>

## Reminders
<Items from STATE.md "Remind Me (Future)" section>

## Blockers / Warnings
<Uncommitted changes, stuck tasks, missing dependencies>
```

7. **Save the briefing** to `todos/morning-briefing.md` (overwrite). Save the previous one to `todos/morning-briefing.prev.md` first if it exists.

8. **Show the briefing** to the user in the chat response.

## Rules

- Keep it concise — this is read before starting work, not a dissertation
- Use checkboxes (`- [ ]`) in Today's Plan so the next briefing can check what got done
- If STATE.md doesn't exist, say so and work from git log + plan only
- If the plan file doesn't exist, work from STATE.md + git log only
- Always save to `todos/morning-briefing.md` even if also showing in chat
