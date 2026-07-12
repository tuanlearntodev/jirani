# Project State — Jirani Offline Library Backend

**Last Updated:** 2026-07-12 15:10 (commit 95fbb75)
**Branch:** refactor
**Uncommitted:** scripts/morning-briefing.sh (fixed: removed --agent general, errors to log file), AGENTS.md (state skill triggers updated), .opencode/skills/state/SKILL.md (commit confirmation trigger added), .opencode/opencode.json (playwright/sequential-thinking MCPs added), todos/ (regenerated briefings), graphify-out/ (auto-regenerated), deleted check.py + video_test.py (Postgres-only cleanup), backend/app/models/book.py + book_tag.py (committed in b5fb6f4 but CRLF line endings show as modified)

## Current State
FastAPI + PostgreSQL backend for an offline library. Auth system fully refactored (Tasks 13-19 done). Book refactor Tasks 2-4 complete — Book model rewritten (2.0 + JSONB + GIN), BookTag cleaned (2.0, is_active dropped), book tables rebuilt in Postgres, Tag model updated to 2.0 style with TYPE_CHECKING guard. 12 of 16 tasks remaining. App is Postgres-only. Opencode tooling configured with 5 MCPs (context7, gh_grep, memory, playwright, sequential-thinking), state skill with commit confirmation trigger, morning briefing automation (fixed: removed --agent general flag, errors now logged to briefing.log).

## In Progress
- [x] **Task 2: Rewrite Book model** — COMPLETE
- [x] **Task 3: Clean up BookTag** — COMPLETE
- [x] **Task 4: Drop and rebuild book tables** — COMPLETE (verified in Postgres: new schema, GIN index, no file_type, no is_active)
- [x] **Tag model updated to 2.0 style** — COMPLETE (bonus cleanup, not a plan task)
- [ ] Tasks 5-16 of the book refactor plan

## Remind Me (Future)
- [ ] Set up Alembic migrations (replaces manual DROP TABLE workflow) (priority: low, added: 2026-07-08)
- [ ] Add StorageService/StorageRepo abstraction for file I/O (currently bypasses service layer) (priority: low, added: 2026-07-08)
- [ ] Normalize repo naming: `Video_Repo` → `VideoRepo` (underscore breaks camelCase convention) (priority: low, added: 2026-07-08)
- [ ] Configure git credential helper to avoid push hanging on other machine (priority: medium, added: 2026-07-08)

## Decisions Log
- 2026-07-12: Fixed morning briefing script — removed `--agent general` flag (was configured as subagent, caused unpredictable fallbacks), changed `2>/dev/null` to `2>"$OUTPUT_DIR/briefing.log"` (errors now visible for debugging). Script now generates clean output reliably.
- 2026-07-12: Added commit confirmation trigger to state skill — "yes", "commit it", "go ahead", "commit please", "push it" now invoke the state skill for a lighter STATE.md update.
- 2026-07-09: Tag model updated to 2.0 style — `Mapped[]` + `mapped_column()`, string type references in relationships with `TYPE_CHECKING` guard for Pylance/mypy type resolution without circular imports.
- 2026-07-09: Dropped `is_active` from `BookTag` — dead column, never queried or toggled. Simplifies the junction table to just `id`, `book_id`, `tag_id` + UniqueConstraint.
- 2026-07-09: Removed `themes` from book refactor plan — `tags` is the single categorization system (subjects + genres in one flat list). Simplified plan from 17 to 16 tasks, eliminated 3 files (theme.py, book_theme.py, theme_schema.py). `metadata_` JSONB remains as extensibility escape hatch.
- 2026-07-09: App is now Postgres-only — removed all SQLite references (config.py default URL, check.py deleted, video_test.py deleted). Docker is the test+ship environment; no WSL venv needed.
- 2026-07-08: Morning briefing automation — output to `todos/morning-briefing.md` (single file, overwritten each morning). Uses `opencode run --format json` piped through Python parser to strip TUI noise. Scheduled via Windows Task Scheduler on logon (not fixed time — PC not always on). Uses `deepseek-v4-flash-free` model ($0/run). Previous briefing saved to `morning-briefing.prev.md` for overdue comparison.
- 2026-07-08: Replaced `opencode-mem` plugin with Memory MCP — opencode-mem was silently broken (sharp native binary missing + OpenAI API key was placeholder `sk-...`, 368 errors in 5 days). Memory MCP uses local JSONL, no external API, no broken dependencies.
- 2026-07-08: Added Playwright + Sequential Thinking MCPs — covers automation (browser) and reasoning (structured step-by-step). Both use `npx` (Node.js 24 LTS installed via nvm).
- 2026-07-08: Replaced `session-handoff` skill with `state` skill — single living STATE.md instead of one-shot handoff.md. Triggered on task completion phrases + "remind me" + "session handoff". Syncs reminders to Memory MCP as TODO entities.
- 2026-07-08: Morning briefing automation via Windows Task Scheduler (logon trigger) — writes to `todos/morning-briefing.md` on every login. No fixed time because PC isn't always on.
- 2026-07-03: Book refactor plan approved — 17 tasks, clean slate (no backward compat), PostgreSQL JSONB for extensibility, god class → 5 focused modules.
- 2026-07-03: Auth refactor completed — /setup endpoint for first-run admin, AuthRepo pattern, RoleChecker on all endpoints, bulk user creation.

## Graveyard (Tried & Didn't Work)
- **Attempt:** `opencode-mem` plugin for cross-session memory — _Why it failed:_ `sharp` native binary not built for linux-x64 in the cached package, AND the OpenAI API key was left as the placeholder `sk-...` from the default config. Both failures were silent (368 errors logged, no user-visible signal). Replaced with Memory MCP which has no native dependencies and no external API.
- **Attempt:** Morning briefing with `--agent general` flag — _Why it failed:_ `general` agent is configured as `subagent` mode in opencode.json. `opencode run` warned "agent is a subagent, not a primary agent" and fell back unpredictably, sometimes producing no text output. Fixed by removing the flag and using the default agent.
- **Attempt:** Morning briefing with `2>/dev/null` — _Why it failed:_ Swallowed all stderr including useful error messages, making it impossible to debug empty output. Fixed by redirecting stderr to `todos/briefing.log`.

## Next Steps
1. [ ] Commit uncommitted changes: scripts/morning-briefing.sh fix, AGENTS.md + state skill update, opencode.json MCPs, deleted files (check.py, video_test.py)
2. [ ] Push to origin
3. [ ] Task 5: Rewrite book schemas (layered + BookSearchCriteria + Page) — `backend/app/schemas/book_schema.py` + `backend/app/schemas/__init__.py`
4. [ ] Task 6: Rewrite BookRepo (dynamic search + pagination + 2.0 style) — `backend/app/repositories/book_repo.py`
5. [ ] Task 7: Create ContentValidator + BookError hierarchy — `backend/app/services/book_errors.py` + `backend/app/services/content_validator.py`
6. [ ] On Mac: `git pull origin refactor && cat STATE.md` to resume
