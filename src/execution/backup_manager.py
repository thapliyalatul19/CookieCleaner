"""Database backup and restore management for Cookie Cleaner."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.core.constants import BACKUPS_DIR

logger = logging.getLogger(__name__)


@dataclass
class BackupResult:
    """Result of a backup operation."""

    db_path: Path
    backup_path: Path
    success: bool
    error: str | None = None


class BackupManager:
    """Manages timestamped backups of cookie databases."""

    def __init__(self, backup_root: Path | None = None) -> None:
        """
        Initialize the BackupManager.

        Args:
            backup_root: Root directory for backups. Defaults to BACKUPS_DIR.
        """
        self.backup_root = backup_root or BACKUPS_DIR

    def create_backup(self, db_path: Path, browser: str, profile: str) -> BackupResult:
        """
        Create a timestamped backup of a database file.

        Backup path format:
            {backup_root}/{browser}/{profile}/{filename}.{timestamp}.bak

        Args:
            db_path: Path to the database file to backup
            browser: Browser name (e.g., "Chrome")
            profile: Profile name (e.g., "Default")

        Returns:
            BackupResult with success status and backup path
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = db_path.name
        backup_filename = f"{filename}.{timestamp}.bak"

        backup_dir = self.backup_root / browser / profile
        backup_path = backup_dir / backup_filename

        try:
            # Create backup directory if it doesn't exist
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Copy the database file
            shutil.copy2(db_path, backup_path)

            logger.info("Created backup: %s -> %s", db_path, backup_path)

            return BackupResult(
                db_path=db_path,
                backup_path=backup_path,
                success=True,
            )
        except FileNotFoundError:
            error = f"Source file not found: {db_path}"
            logger.error(error)
            return BackupResult(
                db_path=db_path,
                backup_path=backup_path,
                success=False,
                error=error,
            )
        except PermissionError as e:
            error = f"Permission denied: {e}"
            logger.error(error)
            return BackupResult(
                db_path=db_path,
                backup_path=backup_path,
                success=False,
                error=error,
            )
        except OSError as e:
            error = f"OS error during backup: {e}"
            logger.error(error)
            return BackupResult(
                db_path=db_path,
                backup_path=backup_path,
                success=False,
                error=error,
            )

    def restore_backup(self, backup_path: Path, db_path: Path) -> bool:
        """
        Restore a database from a backup file.

        Args:
            backup_path: Path to the backup file
            db_path: Path where the database should be restored

        Returns:
            True if restoration succeeded, False otherwise
        """
        try:
            shutil.copy2(backup_path, db_path)
            logger.info("Restored backup: %s -> %s", backup_path, db_path)
            return True
        except FileNotFoundError:
            logger.error("Backup file not found: %s", backup_path)
            return False
        except PermissionError as e:
            logger.error("Permission denied restoring backup: %s", e)
            return False
        except OSError as e:
            logger.error("OS error restoring backup: %s", e)
            return False

    def get_latest_backup(self, browser: str, profile: str) -> Path | None:
        """
        Get the most recent backup for a browser/profile combination.

        Args:
            browser: Browser name (e.g., "Chrome")
            profile: Profile name (e.g., "Default")

        Returns:
            Path to the most recent backup, or None if no backups exist
        """
        backup_dir = self.backup_root / browser / profile

        if not backup_dir.exists():
            return None

        backups = list(backup_dir.glob("*.bak"))
        if not backups:
            return None

        # Sort by modification time, most recent first
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return backups[0]

    def list_backups(self, browser: str | None = None, profile: str | None = None) -> list[Path]:
        """
        List all backups, optionally filtered by browser and profile.

        Args:
            browser: Optional browser name filter
            profile: Optional profile name filter (requires browser)

        Returns:
            List of backup file paths
        """
        if browser and profile:
            search_path = self.backup_root / browser / profile
        elif browser:
            search_path = self.backup_root / browser
        else:
            search_path = self.backup_root

        if not search_path.exists():
            return []

        return list(search_path.rglob("*.bak"))

    def cleanup_old_backups(self, retention_days: int = 7) -> int:
        """
        Remove backups older than the retention period.

        Args:
            retention_days: Number of days to retain backups

        Returns:
            Number of backups deleted
        """
        if retention_days < 0:
            raise ValueError("retention_days must be non-negative")

        cutoff = datetime.now(timezone.utc).timestamp() - (retention_days * 86400)
        deleted_count = 0

        try:
            for backup_file in self.backup_root.rglob("*.bak"):
                try:
                    if backup_file.stat().st_mtime < cutoff:
                        backup_file.unlink()
                        deleted_count += 1
                        logger.debug("Deleted old backup: %s", backup_file)
                except OSError as e:
                    logger.warning("Failed to delete backup %s: %s", backup_file, e)
        except OSError as e:
            logger.warning("Error scanning backup directory: %s", e)

        if deleted_count > 0:
            logger.info("Cleaned up %d old backups", deleted_count)

        # Clean up empty directories
        self._cleanup_empty_dirs()

        return deleted_count

    def _cleanup_empty_dirs(self) -> None:
        """Remove empty directories in the backup tree."""
        if not self.backup_root.exists():
            return

        # Walk bottom-up to remove empty directories
        for dirpath in sorted(self.backup_root.rglob("*"), reverse=True):
            if dirpath.is_dir():
                try:
                    dirpath.rmdir()  # Only removes if empty
                except OSError:
                    pass  # Directory not empty or other error
