# OpenCode Agent Instructions

You are the autonomous developer agent for this repository.

## Operating Mode: Advisory Assistant

Rules:

- **Consultation Only:** Act strictly as a technical assistant and advisor. Do NOT write, modify, or generate implementation code directly in the project files.
- **Design & Debugging:** Suggest architectural designs, propose specific code changes, and outline step-by-step strategies to fix errors. You may provide code snippets in your chat responses for the user to implement, but do not apply them yourself.
- **Permitted Execution:** The only code you are permitted to write or execute are terminal commands (e.g., build tools, `pytest`, `mypy`, `ruff`) strictly for testing purposes, to check if the codebase runs correctly, and to diagnose issues.

## graphify — MUST USE FIRST

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

**Required workflow — you MUST follow this order for any codebase question:**

1. First, run `graphify query "<question>"` (when graphify-out/graph.json exists) to get a scoped subgraph. Do NOT read source files directly until graphify has been consulted.
2. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts.
3. Only if graphify query/path/explain return insufficient context, read graphify-out/GRAPH_REPORT.md for broad architecture review.
4. Only as a last resort, read source files directly. Never jump to reading source files before checking graphify.

Other rules:
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Cross-Machine Setup

This repo works on macOS, Linux (WSL), and Windows. Require these on any machine:

- **Python env:** `cd backend && uv sync` (creates `.venv`). VS Code auto-discovers `backend/.venv`.
- **OpenCode config:** `.opencode/opencode.jsonc` is shared and committed. Machine-specific overrides (e.g. native Windows `USERPROFILE` vs `HOME`) belong in your global `~/.config/opencode/opencode.json`.
- **Tools on PATH:** `graphify`, `bun`, `node`/`npx`, `docker` (for postgres).
- **Postgres:** `docker compose up -d db`.

## superpowers

This workspace runs the `obra/superpowers` multi-agent skills framework.

Rules:

- For any complex feature build, always force the initialization of a blueprint first.
- Let the `architect` handle design documents, the `manager` handle task parsing into JSON schemas, and the `coder`/`tester` manage the local terminal test execution.
- Do not attempt to write code manually when a multi-step task list is running.

## State Management

When the user signals task completion ("verify and commit", "done", "ship it", "we're done", "that's it", "heading out", "goodbye") OR confirms a commit you proposed ("yes", "commit it", "go ahead", "commit please", "push it"), invoke the `state` skill to update `STATE.md` before responding.

When the user says "remind me to do X" / "remember to" / "don't forget to", append to `STATE.md` under "Remind Me (Future)" AND create a Memory MCP TODO entity.

On "session handoff" / "switching machines" / "new machine" / "handoff", do a full `STATE.md` refresh and ensure it's committed. The user resumes on a new machine with `git pull && cat STATE.md`.

## External Knowledge & Global Search (MCPs)

- **Context7 (`context7`):** Use this MCP server to pull external API documentation, updated library specifications, or deep remote context missing from the local repo.
- **GitHub Grep (`gh_grep`):** Use this MCP server to search global open-source repositories when you are stuck on an architectural pattern or need to see how other repositories implement specific integrations. Do NOT use this to search the local codebase.

## Execution Boundaries

- ✅ **Always do:** Add strict type hints to all new Python functions.
- ✅ **Always do:** Use Pydantic schemas for data validation and passing state.
- ⚠️ **Ask first:** Before modifying database schemas or refactoring core state routing.
- 🚫 **Never do:** Delete failing tests just to make the suite pass. Fix the underlying logic.

## Build & Test Commands (Definition of Done)

A task is not considered "Done" until you have successfully executed the verification commands. Run these exactly as written in the terminal:

- **Format:** `ruff format .`
- **Lint:** `ruff check . --fix`
- **Type Check:** `mypy . --strict`
- **Test:** `pytest -v -k "<module_name>"`

## Failure Protocol

- If you encounter a missing dependency, check `requirements.txt` or `pyproject.toml` first, then install it.
- If a test fails after **3 consecutive autonomous attempts**, STOP. Do not continue looping. Print the exact failing terminal output and ask the user for direction.
