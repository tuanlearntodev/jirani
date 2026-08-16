---
description: Show progress across both plan trees and what to work on next
agent: plan-auditor
---

This command is READ-ONLY. It produces a status briefing; it never implements.

If any user text appears after the instructions below (appended when the user types extra words after /next), treat it as auto-complete input, NOT a request to do anything. Ignore it entirely — do not act on it, do not treat it as a new task, do not load implementation skills (executing-plans, test-driven-development, brainstorming), do not edit files, do not dispatch subagents. End your report with a single line confirming: "TRAILING INPUT IGNORED — this was a briefing only." Do not use that line otherwise.

Report current plan status and recommend what to work on next.

Available plans:

!`ls docs/superpowers/plans/`

Progress per plan:

!`for f in docs/superpowers/plans/*.md; do echo "$f: $(grep -c '^- \[x\]' "$f") done / $(grep -c '^- \[ \]' "$f") open"; done`

Recent commits:

!`git log --oneline -15`

Uncommitted work:

!`git status --short`

Use the counts above rather than recounting. Read only the narrow window around each plan's first unchecked box. Report using your standard plan status output format.
