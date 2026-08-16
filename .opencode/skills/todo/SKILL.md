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

2. **Find the active plans.** There is ONE plan tree — `docs/superpowers/plans/`:

   ```bash
   ls docs/superpowers/plans/
   ```

   For each plan file, count progress instead of reading the whole thing (these files run to thousands of lines):

   ```bash
   for f in docs/superpowers/plans/*.md; do
     echo "$f: $(grep -c '^- \[x\]' "$f") done / $(grep -c '^- \[ \]' "$f") open"
   done
   ```

   A plan with zero `[x]` and many `[ ]` has not been started. A plan with no open items is finished — skip it. Read only the sections around the first unchecked box of each plan that still has open work.

   As of 2026-08-16 two plans are in flight: `2026-08-15-codebase-hygiene` (not started) and `2026-08-16-book-refactor`. Verify this with the command above rather than trusting this line.

3. **Run `git log --oneline -20`** — see recent commits to understand what was recently completed.

4. **Run `git status --short`** — see uncommitted work that might need attention.

5. **Read `todos/morning-briefing.prev.md`** if it exists — compare its "Today's Plan" checklist against what actually happened (git log, STATE.md). Any incomplete items go in the Urgent section.

6. **Generate the briefing** with exactly these sections IN THIS ORDER:

```
# Briefing — <Day of week, Month Day Year>

## Urgent (Overdue from last session)
<Any planned steps that were NOT completed. If nothing is overdue, write "Nothing overdue. Good job.">

## Done So Far
<Completed tasks from plan checkboxes + git commits. Name which plan each belongs to.>

## Next Up
<The next incomplete task. Name the plan file AND the task number/title, since more
than one plan is active — "Task 6" alone is ambiguous across two plans.>

## Today's Plan (30 min)
<Break the next task into 3-5 concrete steps with verify commands. Use checkboxes.
Verify commands run from backend/ and start with `uv run` — see AGENTS.md.>

## Reminders
<Items from STATE.md "Remind Me (Future)" section>

## Blockers / Warnings
<Uncommitted changes, stuck tasks, missing dependencies, invariant violations>
```

7. **Save the briefing** to `todos/morning-briefing.md` (overwrite). Save the previous one to `todos/morning-briefing.prev.md` first if it exists.

8. **Show the briefing** to the user in the chat response.

## Rules

- Keep it concise — this is read before starting work, not a dissertation
- Use checkboxes (`- [ ]`) in Today's Plan so the next briefing can check what got done
- If STATE.md doesn't exist, say so and work from git log + plans only
- If no plan file exists, work from STATE.md + git log only
- Always save to `todos/morning-briefing.md` even if also showing in chat
- **Never hardcode a plan path.** Discover plans by listing both trees. A hardcoded path silently goes stale the moment a plan is added, renamed, or finished.
- **Two plans are active.** Always say which plan a task belongs to. Never merge their task numbers into one list.
- When STATE.md and the plan checkboxes disagree, trust the checkboxes and flag the drift under Blockers.
