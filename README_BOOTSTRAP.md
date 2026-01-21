# Cookie Cleaner - Bootstrap Guide

## Overview

This repository implements the Context Architecture OS V4 for the Cookie Cleaner project. All files are now properly created and accessible from Windows.

## Repository Structure

```
C:\dev\cookie-cleaner\
├── .context/              # Memory Bank (4-file temporal state)
│   ├── projectbrief.md    # WHY - Problem, goals, constraints
│   ├── productContext.md  # WHAT - User workflow, UI, state model
│   ├── systemPatterns.md  # HOW - Architecture, patterns, decisions
│   └── activeContext.md   # NOW - Current phase, checklist, next steps
├── .cursor/rules/         # Cursor IDE rules (8 .mdc files)
├── .claude/rules/         # Claude Code CLI rules (8 .mdc files, mirrored)
├── CLAUDE.md              # The Constitution
├── .gitignore             # Git ignore patterns
├── scripts/
│   ├── context-init.sh    # Bootstrap verification (bash)
│   ├── context-init.ps1   # Bootstrap verification (PowerShell)
│   ├── validate-context.sh # Validation script (bash)
│   └── validate-context.ps1 # Validation script (PowerShell)
├── docs/
│   └── PRD_LINK.txt       # Pointer to source PRD
├── src/                   # Application code (to be created)
└── tests/                 # Test suite (to be created)
```

## Quick Start

### 1. Verify All Files Exist

**PowerShell:**
```powershell
cd C:\dev\cookie-cleaner
Get-ChildItem -Recurse -File | Measure-Object
```

**Expected:** 26 files total

### 2. Read the Constitution

```powershell
Get-Content CLAUDE.md
```

### 3. Read Memory Bank

```powershell
Get-Content .context\*.md
```

### 4. Verify Rule Files

```powershell
Get-ChildItem .cursor\rules\*.mdc
Get-ChildItem .claude\rules\*.mdc
```

## Key Files Created

### Memory Bank (.context/)
✅ `projectbrief.md` - Problem statement, goals, platform  
✅ `productContext.md` - User workflow, UI layout, state machine  
✅ `systemPatterns.md` - Architecture layers, data contracts, safety protocols  
✅ `activeContext.md` - Current phase, checklist, recent changes  

### Rule Files (.cursor/rules/ and .claude/rules/)
✅ `000-global-context-hygiene.mdc` - RAU protocol  
✅ `050-repo-conventions.mdc` - Coding standards  
✅ `100-backend-core-contracts.mdc` - Data models  
✅ `120-browser-scanning-boundaries.mdc` - Scanner safety rules  
✅ `150-deletion-safety-locks.mdc` - Deletion safety protocols  
✅ `200-ui-layout-state-machine.mdc` - UI state machine  
✅ `400-testing-golden-fixtures.mdc` - Testing standards  
✅ `900-governance-no-red-zone.mdc` - Red zone protection  

### Configuration Files
✅ `CLAUDE.md` - Constitution (roles, RAU protocol, rules)  
✅ `.gitignore` - Git ignore patterns  
✅ `docs/PRD_LINK.txt` - Link to source PRD  

### Scripts
✅ `scripts/context-init.ps1` - Bootstrap verification  
✅ `scripts/validate-context.ps1` - Pre-commit validation  
✅ `scripts/context-init.sh` - Bootstrap verification (bash)  
✅ `scripts/validate-context.sh` - Pre-commit validation (bash)  

## Next Steps (Phase 1)

### 1. Initialize Git Repository

```powershell
cd C:\dev\cookie-cleaner
git init
git add .
git commit -m "[bootstrap] Initial Context Architecture V4 setup"
```

### 2. Install Pre-Commit Hook

```powershell
# Create hooks directory
New-Item -ItemType Directory -Force -Path .git\hooks

# Create pre-commit hook
@"
#!/bin/bash
./scripts/validate-context.sh
"@ | Out-File -FilePath .git\hooks\pre-commit -Encoding ASCII

# For Git Bash on Windows, the hook should work as-is
```

### 3. Setup Python Environment

```powershell
# Create virtual environment
python -m venv venv

# Activate
.\venv\Scripts\Activate.ps1

# Create requirements.txt
@"
PyQt6>=6.6.0
pycryptodome>=3.19.0
psutil>=5.9.0
pywin32>=306
pytest>=7.4.0
black>=23.12.0
"@ | Out-File -FilePath requirements.txt -Encoding UTF8

# Install dependencies
pip install -r requirements.txt
```

### 4. Verify Bootstrap

```powershell
.\scripts\context-init.ps1
```

## Read-Act-Update (RAU) Protocol

Every code change must follow this loop:

### BEFORE Writing Code
1. Read ALL `.context/*.md` files
2. Read relevant `.mdc` rule files

### AFTER Writing Code, BEFORE Committing
1. Update `.context/activeContext.md` (Recent Changes section)
2. If architectural decision: Update `.context/systemPatterns.md` (Decisions Log)

### AFTER Committing
1. Run `/clear` (in Claude or Cursor)
2. Re-ingest Memory Bank: `Get-Content .context\*.md`

## References

- **PRD:** See `docs\PRD_LINK.txt`
- **Operational Guide:** `C:\Users\thapl\OneDrive\Documents\Obsidian\Obsidian Vault 1\CLAUDE_CODE_OPERATIONAL_GUIDE_V4.md`
- **Constitution:** `CLAUDE.md`
- **Memory Bank:** `.context\*.md`

---

**Last Updated:** 2026-01-21  
**Bootstrap Version:** V4  
**Status:** ✅ Complete and Ready for Phase 1
