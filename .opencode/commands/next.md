---
description: Show progress across both plan trees and what to work on next
agent: plan-auditor
---

Report current plan status and recommend what to work on next.

Available plans:

!`ls docs/plans/ docs/superpowers/plans/`

Progress per plan:

!`for f in docs/plans/*.md docs/superpowers/plans/*.md; do echo "$f: $(grep -c '^- \[x\]' "$f") done / $(grep -c '^- \[ \]' "$f") open"; done`

Recent commits:

!`git log --oneline -15`

Uncommitted work:

!`git status --short`

Use the counts above rather than recounting. Read only the narrow window around each plan's first unchecked box. Report using your standard plan status output format.
