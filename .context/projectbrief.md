# Project Brief

## Status: Initialized - Phase 1 (Environment & Foundation)

## Problem Statement

Web browsers accumulate thousands of cookies. Users want to clear privacy-invasive tracking cookies but fear losing login sessions (MFA tokens, session IDs) for frequently used sites. Existing browser tools are too "all-or-nothing," leading to user friction and repeated re-authentication.

## Project Goals

1. **Discovery:** Enumerate cookies from all major browsers (Chrome, Firefox, Edge, Brave, Opera, Vivaldi) and _all_ associated user profiles.
2. **Aggregation:** Display cookies organized by domain in a unified interface.
3. **Whitelisting:** Provide a robust grammar to preserve login sessions and preferences.
4. **Secure Deletion:** Selectively remove non-whitelisted cookies only when browsers are closed, backed by mandatory recovery snapshots.
5. **Persistence:** Maintain configurations and audit logs across sessions.

## Target Platform

- **OS:** Windows 10/11 Desktop
- **Stack:** Python 3.11+, PyQt6, SQLite3, pycryptodome (decryption), psutil (safety), pywin32 (lock detection), PyInstaller (packaging)
- **Distribution:** Standalone executable via PyInstaller

## Safety-First Principle

This application handles sensitive user data (authentication cookies). All operations must be:
- **Non-destructive by default:** Dry-run mode, backup-before-delete
- **Process-aware:** Block operations while browsers are running
- **Recoverable:** Automatic backup snapshots before any database modification
- **Auditable:** Comprehensive logging of all operations

## Project Constraints

- Single-user Windows desktop application (no client-server)
- No cloud sync or external dependencies beyond Python packages
- Must handle browser-specific quirks (DPAPI decryption, profile discovery)
- Must gracefully handle locked database files
