---
name: session-handoff
description: Generates a handoff.md file summarizing the current development session for transitioning to a new machine.
compatibility: opencode
---

## What I do

- Analyze the current session's conversation history and recently edited files.
- Deduce the primary objective, working state, failed attempts, and current blockers.
- Write a `handoff.md` file in the root directory.

## When to use me

Use this when wrapping up a development session or preparing to switch machines.

## Instructions

1. Gather context from our recent interactions in the terminal.
2. Determine the active project and the primary tech stack being used.
3. Generate a file named `handoff.md` using the exact template below:

# 🔄 Session Handoff

**Date:** [Current Date]
**Project:** [Project Name]
**Primary Tech Stack:** [Tech Stack]

## 🎯 Current Objective

> _What was the primary goal of this development session?_

- [Analysis of our primary goal]

## ✅ What Was Accomplished (Working State)

- **[Component]:** [What was built/fixed]

## 🧪 What Was Tried & Didn't Work (The Graveyard)

- **Attempt:** [Failed approach]
  - _Why it failed:_ [Reason]

## 🚧 Currently Working On (Work In Progress)

- **Active File(s):** `[Recent files]`
- **Current State:** [Where we left off]
- **Open Problem:** [Current bug or block]

## ⏭️ Next Steps (Action Items for New Machine)

1. [ ] [Immediate next technical step]
2. [ ] [Secondary step]
3. [ ] Run integration tests and verify.

## 💻 Environment & Git Notes

- **Branch:** [Current git branch]
- **Uncommitted Changes:** [List of uncommitted files]
