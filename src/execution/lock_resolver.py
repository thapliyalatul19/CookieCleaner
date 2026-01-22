"""Database lock detection for Cookie Cleaner."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import psutil

try:
    import win32file
    import pywintypes
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

logger = logging.getLogger(__name__)

# Error code for sharing violation (file locked)
ERROR_SHARING_VIOLATION = 32

# Mapping of path fragments to browser executables
BROWSER_PATH_MAPPINGS = {
    "chrome": "chrome.exe",
    "google\\chrome": "chrome.exe",
    "microsoft\\edge": "msedge.exe",
    "edge": "msedge.exe",
    "brave": "brave.exe",
    "brave-browser": "brave.exe",
    "opera": "opera.exe",
    "opera software": "opera.exe",
    "vivaldi": "vivaldi.exe",
    "firefox": "firefox.exe",
    "mozilla\\firefox": "firefox.exe",
}


@dataclass
class LockReport:
    """Result of a lock check on a database file."""

    db_path: Path
    is_locked: bool
    error_code: int | None = None
    blocking_processes: list[str] = field(default_factory=list)

    @property
    def can_proceed(self) -> bool:
        """Return True if the database is not locked."""
        return not self.is_locked


class LockResolver:
    """Detects if cookie databases are locked by running browser processes."""

    def __init__(self) -> None:
        """Initialize the LockResolver."""
        if not HAS_WIN32:
            logger.warning("pywin32 not available - lock detection will use fallback method")

    def check_lock(self, db_path: Path) -> LockReport:
        """
        Check if a database file is locked.

        Args:
            db_path: Path to the database file

        Returns:
            LockReport with lock status and blocking processes
        """
        if not db_path.exists():
            return LockReport(
                db_path=db_path,
                is_locked=False,
                error_code=None,
                blocking_processes=[],
            )

        is_locked = False
        error_code = None
        blocking_processes = []

        if HAS_WIN32:
            is_locked, error_code = self._check_with_win32(db_path)
        else:
            is_locked = self._check_with_open(db_path)

        if is_locked:
            blocking_processes = self._find_blocking_processes(db_path)

        return LockReport(
            db_path=db_path,
            is_locked=is_locked,
            error_code=error_code,
            blocking_processes=blocking_processes,
        )

    def check_all(self, db_paths: list[Path]) -> list[LockReport]:
        """
        Check multiple database files for locks.

        Args:
            db_paths: List of database paths to check

        Returns:
            List of LockReports for each path
        """
        return [self.check_lock(path) for path in db_paths]

    def get_running_browsers(self) -> set[str]:
        """
        Get the set of currently running browser executables.

        Returns:
            Set of browser executable names (e.g., {"chrome.exe", "firefox.exe"})
        """
        browsers = set()
        browser_names = {
            "chrome.exe", "msedge.exe", "brave.exe",
            "firefox.exe", "opera.exe", "vivaldi.exe",
        }

        try:
            for proc in psutil.process_iter(["name"]):
                try:
                    name = proc.info["name"]
                    if name and name.lower() in browser_names:
                        browsers.add(name.lower())
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.warning("Error enumerating processes: %s", e)

        return browsers

    def _check_with_win32(self, db_path: Path) -> tuple[bool, int | None]:
        """
        Check file lock using win32 API.

        Returns:
            Tuple of (is_locked, error_code)
        """
        try:
            handle = win32file.CreateFile(
                str(db_path),
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,  # No sharing - exclusive access
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )
            win32file.CloseHandle(handle)
            return False, None
        except pywintypes.error as e:
            error_code = e.winerror
            if error_code == ERROR_SHARING_VIOLATION:
                return True, error_code
            # Other errors (file not found, access denied, etc.)
            logger.debug("Win32 error checking %s: %s", db_path, e)
            return False, error_code

    def _check_with_open(self, db_path: Path) -> bool:
        """
        Fallback lock check using Python's open().

        Returns:
            True if file appears to be locked
        """
        try:
            with open(db_path, "r+b"):
                return False
        except PermissionError:
            return True
        except OSError:
            return False

    def _find_blocking_processes(self, db_path: Path) -> list[str]:
        """
        Find browser processes likely blocking the database.

        Args:
            db_path: Path to the locked database

        Returns:
            List of browser executable names that may be blocking
        """
        blocking = []
        db_path_lower = str(db_path).lower()

        # Determine which browser this database belongs to
        browser_exe = None
        for fragment, exe in BROWSER_PATH_MAPPINGS.items():
            if fragment in db_path_lower:
                browser_exe = exe
                break

        if browser_exe:
            running = self.get_running_browsers()
            if browser_exe.lower() in running:
                blocking.append(browser_exe)
        else:
            # Unknown browser - report all running browsers
            blocking = list(self.get_running_browsers())

        return blocking
