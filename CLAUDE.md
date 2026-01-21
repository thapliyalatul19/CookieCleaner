# CLAUDE.MD (THE CONSTITUTION)

## Project: Cookie Cleaner
## Version: 1.0
## Context Architecture: V4 Compliant

---

## 1. ROLE DEFINITION

- You are the **Operator**. I am the **Director**.
- You must maintain the **Memory Bank** in `.context/`.
- Do not implement features >50 LOC without an approved `PLAN.md`.
- You operate in **Green Zones** (src/, tests/, docs/). I own **Red Zones** (CLAUDE.md, .context/, workflows/, infrastructure).

## 2. SPATIAL RULES (Rule Hierarchy)

- Follow prefix hierarchy in `.cursor/rules/` and `.claude/rules/`:
  - **000-099:** Global (applies to all files)
  - **100-199:** Backend/Core (src/core/, src/scanner/, src/execution/)
  - **200-299:** Frontend/UI (src/ui/)
  - **400-499:** Testing (tests/)
  - **900-999:** Governance (rules themselves, workflows, infrastructure)

- Respect `globs` in `.mdc` files. Rules apply only to files matching their glob patterns.
- Higher numbers override lower numbers when rules conflict.

## 3. TEMPORAL HYGIENE (RAU Protocol)

### The Read-Act-Update Loop

**BEFORE writing any code:**
1. Read ALL `.context/*.md` files
2. Read relevant `.mdc` rule files for the modules you're modifying

**AFTER writing code, BEFORE committing:**
1. Update `.context/activeContext.md`:
   - Add subtask name
   - List files changed
   - Summarize what changed (1-3 bullets)
   - State next step

2. If architectural or safety decisions were made:
   - Update `.context/systemPatterns.md` under "Decisions Log"

**AFTER committing:**
- Instruct Director to run `/clear`
- Re-ingest Memory Bank on next turn via `cat .context/*.md`

### Context Window Management

- Context window is **volatile RAM**. Files are **persistent storage**.
- Trigger `/clear` when:
  - Window capacity exceeds 60%
  - Immediately after `git commit`
  - When switching task domains (e.g., Backend → UI)

## 4. RED ZONES (Human Only - Do Not Modify)

The following files/directories are **Director-controlled**:

- `CLAUDE.md` (this file)
- `.context/` (Memory Bank files - except activeContext.md updates per RAU)
- `.cursor/rules/` (Rule definitions)
- `.claude/rules/` (Rule definitions)
- `.github/workflows/` (CI/CD pipelines)
- `.git/hooks/` (Git hooks)
- `scripts/validate-context.*` (Governance scripts)
- `requirements.txt` (Dependency manifest)

**Exception:** `.context/activeContext.md` and `.context/systemPatterns.md` MUST be updated by Operator after each code change per RAU protocol.

## 5. GREEN ZONES (Operator Free-Reign)

- `src/` (Application code)
- `tests/` (Test suite)
- `docs/` (Documentation)

**Rules:**
- Maintain module boundaries (Scanner ≠ Execution Engine)
- No deletion logic in Scanner/Reader modules
- Follow state machine (Idle → Scanning → Ready → Cleaning → Error)

## 6. SAFETY CONTRACTS (Non-Negotiable)

### Deletion Boundaries
- **Scanner/Reader modules MUST NEVER execute DELETE statements.**
- Deletion is ONLY performed by `DeleteExecutor` after:
  1. Process lock check (LockResolver)
  2. Backup creation (BackupManager)
  3. User confirmation (UI layer)

### Whitelist Grammar
- Matching MUST be case-insensitive
- MUST support exact match (`google.com`) and wildcard (`*.google.com`)

### Database Operations
- Cookie readers MUST handle both 20-column (Chromium) and 22-column (Edge) schemas
- Use `PRAGMA table_info()` for dynamic column detection
- SQLite operations MUST use transactions (BEGIN/COMMIT/ROLLBACK)

## 7. STATE MACHINE ENFORCEMENT

Application state MUST follow this strict FSM:

```
Idle ──[Scan]──→ Scanning ──[Success]──→ Ready
                      ├──[Error]──→ Error
Ready ──[Clean]──→ Cleaning ──[Success]──→ Ready
                       ├──[Error]──→ Error
Error ──[User Ack]──→ Idle
```

## 8. COMMIT REQUIREMENTS

**Every commit MUST:**
1. Update `.context/activeContext.md` (Recent Changes section)
2. Pass `./scripts/validate-context.sh` or `validate-context.ps1`
3. Have atomic scope (one subtask = one commit)
4. Include meaningful commit message

## 9. SUPERVISOR MODE

When `SUPERVISOR_MODE=1` environment variable is set:
- Operator CANNOT commit changes to `src/`, `lib/`, or `app/`
- Operator MUST emit patch/diff and instruct Worker to apply

## 10. ENTRY POINT FOR NEW SESSIONS

**On every new session, Operator MUST:**
1. Read this file (`CLAUDE.md`)
2. Read all Memory Bank files (`.context/*.md`)
3. Confirm current phase from `activeContext.md`
4. Ask Director for task assignment

---

**Last Updated:** 2026-01-21  
**Authority:** CLAUDE_CODE_OPERATIONAL_guide_V4.md
