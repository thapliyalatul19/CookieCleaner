# System Patterns

## Status: Initialized - Phase 1 (Environment & Foundation)

## Architecture Layers

### 1. GUI Layer (PyQt6)
- **Responsibility:** User interaction and background thread orchestration
- **Components:** MainWindow, ScanWorker, CleanWorker
- **Key Pattern:** QThread-based background operations to prevent UI blocking

### 2. Cookie Manager (Core)
- **Responsibility:** Logic for aggregation, whitelist matching, and Delete Plan generation
- **Components:** CookieAggregator, WhitelistManager, DeletePlanner
- **Key Pattern:** Domain normalization (strip leading dots, lowercase)

### 3. Browser Scanner
- **Responsibility:** Low-level filesystem discovery for profiles and cookie databases
- **Components:** BrowserDetector, ProfileResolver, ChromiumReader, FirefoxReader
- **Key Pattern:** Iterator-based profile discovery (not hardcoded "Default" folder)

### 4. Secure Deletion Engine
- **Responsibility:** File locking checks, backups, and atomic SQLite transactions
- **Components:** DeleteExecutor, BackupManager, LockResolver
- **Key Pattern:** Backup-before-delete, rollback on failure

## Data Contracts

### BrowserStore
```python
@dataclass
class BrowserStore:
    browser_name: str      # "Chrome", "Firefox", "Edge", etc.
    profile_id: str        # "Default", "Profile 1", etc.
    db_path: Path          # Full path to cookie database
    is_chromium: bool      # Determines reader strategy
    local_state_path: Optional[Path]  # For DPAPI key (Chromium only)
```

### CookieRecord
```python
@dataclass
class CookieRecord:
    domain: str            # Normalized: "google.com"
    raw_host_key: str      # As stored: ".google.com"
    name: str              # Cookie name
    store: BrowserStore    # Source reference
    expires: Optional[datetime]
    is_secure: bool
```

### DomainAggregate
```python
@dataclass
class DomainAggregate:
    normalized_domain: str     # "google.com" (for display/matching)
    cookie_count: int          # Total across all sources
    browsers: Set[str]         # {"Chrome", "Firefox"}
    records: List[CookieRecord]
    raw_host_keys: Set[str]    # {".google.com", "google.com"}
```

## Safety Protocols

### 1. Lock Detection (Pre-Execution)
- **When:** Before any delete operation
- **How:** LockResolver checks file locks via pywin32
- **Outcome:** If locked → block operation, show error with process names

### 2. Backup Policy (Mandatory)
- **When:** Before every delete operation
- **How:** Copy entire cookie database to timestamped backup folder
- **Outcome:** If delete fails → restore from backup

### 3. Atomic Transactions (SQLite)
- **When:** During delete execution
- **How:** Wrap all DELETE statements in BEGIN/COMMIT
- **Outcome:** On error → ROLLBACK, no partial deletes

## Non-Negotiables

### Deletion Boundaries
- **Rule:** Scanner/Reader modules MUST NEVER execute DELETE statements
- **Enforcement:** Code review + module tests

### Whitelist Grammar
- **Rule:** Matching MUST be case-insensitive
- **Rule:** MUST support both exact match and wildcard patterns

### Schema Tolerance
- **Rule:** Cookie readers MUST handle both 20-column (Chromium) and 22-column (Edge) schemas
- **Rule:** MUST use dynamic column detection via `PRAGMA table_info()`

## Decisions Log

### 2026-01-21: Repository Initialized
- **Decision:** Create repo outside OneDrive to avoid sync conflicts
- **Location:** `C:\dev\cookie-cleaner`
- **Rationale:** Obsidian vault is read-only source of truth; working repo must be independent

### 2026-01-21: Memory Bank Seeded from PRD v1.4
- **Source:** `Cookie_Cleaner_PRD 1.3.md` (actually v1.4 per header)
- **Content:** Extracted problem statement, goals, architecture, state model, safety protocols
- **Next:** Phase 1 implementation (environment setup, profile resolver, data models)
