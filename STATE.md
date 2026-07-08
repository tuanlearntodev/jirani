# Project State — Jirani Offline Library Backend

**Last Updated:** 2026-07-08 14:22 (commit adfdb40)
**Branch:** refactor
**Uncommitted:** book.py, tag.py (WIP book refactor Task 2, not part of this commit), graphify-out/ (auto-regenerated), opencode package files, docs/plans + docs/specs (pre-existing changes)

## Current State
FastAPI + PostgreSQL backend for an offline library. Auth system fully refactored (Tasks 13-19 done: /setup endpoint, AuthRepo, role-based access, bulk user creation). Book refactor is in progress — Task 2 (rewrite Book model) started but incomplete, 15 of 17 tasks remaining. Opencode tooling is configured with 5 MCPs (context7, gh_grep, memory, playwright, sequential-thinking), state skill for session management, and morning briefing automation.

## In Progress
- [ ] **Task 2: Rewrite Book model** (SQLAlchemy 2.0 + JSONB) — started but broken: still has `file_type` column (should be dropped), missing `TimestampMixin`, missing JSONB `metadata_`, missing `themes` relationship, missing GIN index, `author`/`level`/`book_type` are `nullable=False` (should be nullable)
- [ ] Tasks 3-17 of the book refactor plan

## Remind Me (Future)
- [ ] Set up Alembic migrations (replaces manual DROP TABLE workflow) (priority: low, added: 2026-07-08)
- [ ] Add StorageService/StorageRepo abstraction for file I/O (currently bypasses service layer) (priority: low, added: 2026-07-08)
- [ ] Normalize repo naming: `Video_Repo` → `VideoRepo` (underscore breaks camelCase convention) (priority: low, added: 2026-07-08)
- [ ] Configure git credential helper to avoid push hanging on other machine (priority: medium, added: 2026-07-08)

## Decisions Log
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
1. [ ] Fix Task 2: rewrite `backend/app/models/book.py` per plan spec (drop `file_type`, add `TimestampMixin`, add JSONB `metadata_` with GIN index, add `themes` relationship, make `author`/`level`/`book_type`/`language` nullable, use full UUID4)
2. [ ] Task 3: Create `Theme` + `BookTheme` models, clean up `BookTag` to 2.0 style
3. [ ] Task 4: Drop and rebuild book tables in PostgreSQL
4. [ ] Commit scripts/ (morning-briefing.sh + .bat) and STATE.md to refactor branch
5. [ ] Push refactor branch to origin (requires git credential setup — push hung last time)
