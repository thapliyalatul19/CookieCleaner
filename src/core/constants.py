"""Application constants and paths for Cookie Cleaner."""

import os
from pathlib import Path

# Application metadata
APP_NAME = "CookieCleaner"
APP_VERSION = "1.0.0"
CONFIG_VERSION = 1

# Base paths
APPDATA_ROOT = Path(os.environ.get("APPDATA", "")) / APP_NAME
CONFIG_DIR = APPDATA_ROOT
LOGS_DIR = APPDATA_ROOT / "logs"
BACKUPS_DIR = APPDATA_ROOT / "backups"

# File paths
CONFIG_FILE = CONFIG_DIR / "config.json"
DEBUG_LOG_FILE = LOGS_DIR / "debug.log"
AUDIT_LOG_FILE = LOGS_DIR / "audit.log"

# Logging settings
DEBUG_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
DEBUG_LOG_BACKUP_COUNT = 3

# Valid whitelist prefixes
VALID_WHITELIST_PREFIXES = frozenset({"domain:", "exact:", "ip:"})

# Default whitelist (from PRD Appendix B)
DEFAULT_WHITELIST = [
    "domain:google.com",
    "domain:live.com",
    "domain:microsoft.com",
    "domain:amazon.com",
    "domain:github.com",
    "ip:192.168.1.1",
]

# Default settings
DEFAULT_SETTINGS = {
    "confirm_before_clean": True,
    "backup_retention_days": 7,
    "theme": "system",
}

# Browser executable names for process detection
BROWSER_EXECUTABLES = frozenset({
    "chrome.exe",
    "msedge.exe",
    "brave.exe",
    "firefox.exe",
    "opera.exe",
    "vivaldi.exe",
})
