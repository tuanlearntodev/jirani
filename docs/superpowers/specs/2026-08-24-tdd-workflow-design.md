# Test-Driven Development Workflow — Design Spec (2026-08-24)

Status: approved (brainstorming session 2026-08-24). Implements user request
"change this into test driven development after book refactor. and tdd with
refactoring both audio and video feature of the software."

## Problem

The book-refactor plan is written red-green per task (failing test first, then
implementation, verified pass — see `docs/superpowers/plans/2026-08-16-book-refactor.md`
Tasks 0–5), but nothing in AGENTS.md binds that pattern for future work. The
superpowers `test-driven-development` skill is installed but not wired into the
project workflow. Audio/video/tag have zero tests (invariant 5's "violating
today" column) and are booked for a future refactor in the debt ledger.

## Decisions (user-approved)

1. **Scope — both.** AGENTS.md makes test-first a binding rule for all future
   feature/bugfix work, AND the first project executed under the rule is the
   audio/video/tag refactor.
2. **Legacy handling — characterization first.** Refactoring untested code
   starts by pinning current behavior (including known-broken behavior,
   recorded as documented bugs), then refactors under the pin, fixing each bug
   red-first. Matches and operationalises invariant 5's existing
   characterization rule. (Rejected: pure red-green everywhere, which silently
   changes current quirks such as tag OR/AND semantics; and characterize-only-
   endpoints, which leaves legacy internals unpinned.)
3. **Mechanism — Approach B, a binding workflow section in AGENTS.md** (not a
   seventh invariant — process rules belong with process rules, not in the
   code-structure table; not advisory practice — the user wants a real change).
4. **Tag included** in the audio/video project (later session), matching the
   book plan's Deferred Work D1 bundle and the debt ledger's "future
   audio/video/tag plan" wording.

## What ships in this change

### 1. New AGENTS.md section: `## Test-Driven Development (binding)`

Placed after `## Best Practices`. Content:

- **Iron Law:** no production code without a failing test first; a test that
  passes immediately on first run proves nothing.
- **Red-Green-Refactor:** RED (one failing test, one behavior) → verify red for
  the expected reason → GREEN (minimal code) → verify green → REFACTOR keeping
  green. Commit per completed cycle; never commit production code whose test
  was not witnessed failing first.
- **Characterization first for legacy code:** pin current behavior (including
  documented bugs), then refactor under the pin, fixing bugs red-first.
- **Plans are written red-green:** every plan task producing code has the shape
  write-failing-test → record red output → implement → record green →
  lint/type → commit. Book-refactor Tasks 0–5 are the reference pattern.
- **Coder briefs are red-first:** brief block names the failing test as the
  first artifact and a VERIFY command expected to fail before implementation.
- **DoD gate:** every new/changed function is covered by a test witnessed
  failing (red) before the code made it pass (green); `verifier` reports on it.

### 2. Invariant 5 touch

Append pointer to the TDD section (characterization-first for legacy,
red-green for new behavior).

### 3. Coder brief template touch

`--- CODER BRIEF ---` block gains a `RED-FIRST:` line naming the test file and
expected red reason (or "none — characterization pin").

### 4. Verifier wiring

`.opencode/agent/verifier.md` gains a TDD-gate check: a change with no recorded
red evidence (except characterization pins) is NOT DONE. This is the
enforcement half of the DoD gate.

## Explicitly deferred (later session: audio/video/tag refactor)

- The audio/video/tag refactor itself: service layers (invariant 1), naming
  `Audio_Repo`→`AudioRepo` etc. (invariant 6), SQLAlchemy 2.0 (invariant 4),
  delete-missing 500s, full test suites (invariant 5).
- `.opencode/agent/coder.md` prompt hardening (RED-FIRST execution discipline)
  — AGENTS.md states the rule; the agent-prompt wiring lands with that session.
- Debt-ledger rows for audio/video/tag stay owned by the future plan.
