# Project State — Jirani Offline Library Backend

**Last Updated:** 2026-07-09 19:02 (commit 9b32736)
**Branch:** refactor
**Uncommitted:** tag.py (WIP, not part of this commit), graphify-out/ (auto-regenerated), opencode package files

## Current State
FastAPI + PostgreSQL backend for an offline library. Auth system fully refactored (Tasks 13-19 done). Book refactor Tasks 2-3 complete — Book model rewritten in SQLAlchemy 2.0 with JSONB + GIN index, BookTag cleaned to 2.0 style with dead `is_active` dropped. 13 of 16 tasks remaining. App is Postgres-only. Opencode tooling configured with 5 MCPs, state skill, morning briefing automation.

## In Progress
- [x] **Task 2: Rewrite Book model** — COMPLETE (verified: columns, GIN index, JSONB, timestamps, nullability all pass)
- [x] **Task 3: Clean up BookTag** — COMPLETE (verified: 2.0 style, is_active dropped, UniqueConstraint present)
- [ ] Tasks 4-16 of the book refactor plan

## Remind Me (Future)
- [ ] Set up Alembic migrations (replaces manual DROP TABLE workflow) (priority: low, added: 2026-07-08)
- [ ] Add StorageService/StorageRepo abstraction for file I/O (currently bypasses service layer) (priority: low, added: 2026-07-08)
- [ ] Normalize repo naming: `Video_Repo` → `VideoRepo` (underscore breaks camelCase convention) (priority: low, added: 2026-07-08)
- [ ] Configure git credential helper to avoid push hanging on other machine (priority: medium, added: 2026-07-08)

## Decisions Log
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

## Next Steps
1. [ ] Task 4: Drop and rebuild book tables in PostgreSQL (requires Docker)
2. [ ] Task 5: Rewrite book schemas (layered + BookSearchCriteria + Page)
3. [ ] Task 6: Rewrite BookRepo (dynamic search + pagination + 2.0 style)
4. [ ] Push refactor branch to origin
