# Product Context

## Status: Initialized - Phase 1 (Environment & Foundation)

## User Workflow

1. **Launch:** App loads configuration and previous whitelist.
2. **Scan:** App crawls filesystem for browser profiles and reads SQLite databases.
3. **Review:** Left panel shows domains to delete; Right panel shows domains to keep.
4. **Manage:** User transfers domains between panels (Drag/Drop, Arrows, Double-click).
5. **Clean:** App generates a Delete Plan, prompts to close browsers, backs up files, and executes deletion.
6. **Verify:** Result report is displayed; results are logged to the Audit Log.

## UI Layout

### Main Window Structure

```
┌─────────────────────────────────────────────────────┐
│ Cookie Cleaner                              [_][□][X]│
├─────────────────────────────────────────────────────┤
│ [Scan Browsers]  [Clean Now]  Status: Ready         │
├──────────────────────┬──────────────────────────────┤
│ DELETE LIST          │ KEEP LIST (Whitelist)        │
│ ┌──────────────────┐ │ ┌──────────────────────────┐ │
│ │ ☐ doubleclick.net│ │ │ ☑ accounts.google.com    │ │
│ │   (12 cookies)   │ │ │   (5 cookies)            │ │
│ │ ☐ facebook.com   │ │ │ ☑ github.com             │ │
│ │   (8 cookies)    │ │ │   (3 cookies)            │ │
│ └──────────────────┘ │ └──────────────────────────┘ │
│                      │                              │
│ [←] [→]     [Search: ___________]                   │
└─────────────────────────────────────────────────────┘
```

## State Model & Transitions

| State | Allowed Transitions | Description | UI Behavior |
|-------|---------------------|-------------|-------------|
| **Idle** | → Scanning | Initial state or after clean operation | Scan enabled; Clean disabled |
| **Scanning** | → Ready, → Error | Traversing directories and reading databases | All buttons disabled; Progress bar active |
| **Ready** | → Scanning, → Cleaning | Scan complete; lists populated | Scan and Clean enabled |
| **Cleaning** | → Ready, → Error | Backing up and executing SQL deletes | Buttons disabled; Status: "Backing up..." |
| **Error** | → Scanning, → Idle | Critical failure (e.g., File Locked) | Show dialog; Reset to Idle |

## UX Constraints

### Interaction Patterns
1. **Drag & Drop:** Users can drag domains between Delete/Keep lists
2. **Arrow Buttons:** Move selected domains left (→ Keep) or right (→ Delete)
3. **Double-Click:** Toggle domain between lists
4. **Search/Filter:** Real-time filtering of domain lists
5. **Bulk Selection:** Checkbox to select all visible domains

### Safety Prompts
1. **Browser Running:** "Please close all browsers before cleaning. Open browsers: Chrome, Firefox"
2. **Confirm Delete:** "About to delete X cookies from Y domains across Z browsers. Continue?"
3. **Backup Location:** "Backups saved to: C:\Users\...\CookieCleaner\backups\"

## Feature Requirements

### Core Features (MVP)
- Multi-browser detection (Chrome, Firefox, Edge, Brave, Opera, Vivaldi)
- Multi-profile discovery (all profiles, not just Default)
- Domain aggregation across all browsers/profiles
- Dual-list UI (Delete vs Keep)
- Process detection (block if browsers running)
- Automatic backup before deletion
- Audit log
