#!/usr/bin/env bash
# Morning briefing — reads STATE.md + plan + git log, outputs a focused daily plan.
# Run via cron or Windows Task Scheduler.

set -euo pipefail

REPO_DIR="/mnt/d/jirani_offline_library_backend"
OUTPUT_DIR="$REPO_DIR/todos"
OUTPUT_FILE="$OUTPUT_DIR/morning-briefing.md"
PREV_FILE="$OUTPUT_DIR/morning-briefing.prev.md"

mkdir -p "$OUTPUT_DIR"

cd "$REPO_DIR"

# Save the previous briefing for comparison before overwriting
if [ -f "$OUTPUT_FILE" ]; then
  cp "$OUTPUT_FILE" "$PREV_FILE"
fi

# Pull latest if on a shared branch (so briefing reflects other machine's work)
git pull --ff-only origin refactor 2>/dev/null || true

# Check if a previous briefing exists for the "Urgent" section
PREV_FLAG="no"
if [ -f "$PREV_FILE" ]; then
  PREV_FLAG="yes"
fi

# Run opencode in non-interactive mode (JSON output, extract only the final assistant message)
opencode run "You are generating a morning briefing for the Jirani Offline Library Backend project.
This file will be OVERWRITTEN every morning, so make it a clean snapshot of today's status.

Start the file with this exact header:
# Morning Briefing — $(date '+%A, %B %d %Y')

Then read these sources:
1. STATE.md (if it exists) — current project state, in-progress tasks, reminders
2. docs/plans/2026-07-03-book-refactor-plan.md — the 17-task book refactor plan
3. Run 'git log --oneline -20' to see recent commits
4. Run 'git status --short' to see uncommitted work
$(if [ "$PREV_FLAG" = "yes" ]; then
echo "5. todos/morning-briefing.prev.md — YESTERDAY'S briefing. Read it carefully."
fi)

Then output a markdown briefing with exactly these sections IN THIS ORDER:

## Urgent (Overdue from last session)
$(if [ "$PREV_FLAG" = "yes" ]; then
echo "Read todos/morning-briefing.prev.md. Compare its 'Today's Plan' checklist against what actually happened (git log, STATE.md, uncommitted files). Any step that was planned but NOT completed goes here. If everything was done, write 'Nothing overdue. Good job.' This section MUST come first — before today's plan — so nothing gets forgotten."
else
echo "No previous briefing found. Write 'First run — no overdue items.'"
fi)

## Done So Far
List completed tasks (check plan checkboxes + git commits).

## Next Up
The next incomplete task from the plan. Include its task number and title.

## Today's Plan (30 min)
Break the next task into 3-5 concrete steps, each doable in ~10 minutes.
Include the verify command for each step. Use a checklist so tomorrow's briefing can check what got done.

## Reminders
Any items from STATE.md 'Remind Me (Future)' section, if STATE.md exists.

## Blockers / Warnings
Any uncommitted changes that look risky, any tasks that seem stuck.

Keep it concise. This is read over coffee, not a dissertation.
Output ONLY the markdown briefing. No commentary, no preamble, no postscript." \
  --dir "$REPO_DIR" \
  --agent general \
  --model "opencode/deepseek-v4-flash-free" \
  --format json 2>/dev/null | \
  python3 -c "
import sys, json

texts = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        continue
    # opencode JSON format: top-level type='text', text in part.text
    if event.get('type') == 'text':
        part = event.get('part', {})
        text = part.get('text', '')
        if text and text.strip():
            texts.append(text)

# Write the last text block (the final briefing)
if texts:
    print(texts[-1])
else:
    print('ERROR: No text output from opencode run')
" > "$OUTPUT_FILE"

echo "Briefing saved to $OUTPUT_FILE"
