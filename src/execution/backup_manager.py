"""Database backup and restore management for Cookie Cleaner."""

from __future__ import annotations

import json
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

            # Also backup WAL and SHM files if they exist
            wal_path = Path(str(db_path) + "-wal")
            shm_path = Path(str(db_path) + "-shm")

            if wal_path.exists():
                wal_backup = Path(str(backup_path) + "-wal")
                shutil.copy2(wal_path, wal_backup)
                logger.debug("Backed up WAL file: %s", wal_backup)

            if shm_path.exists():
                shm_backup = Path(str(backup_path) + "-shm")
                shutil.copy2(shm_path, shm_backup)
                logger.debug("Backed up SHM file: %s", shm_backup)

            # Write metadata file with original path info
            meta_path = Path(str(backup_path) + ".meta")
            metadata = {
                "original_db_path": str(db_path),
                "browser": browser,
                "profile": profile,
                "timestamp": timestamp,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            meta_path.write_text(json.dumps(metadata, indent=2))
            logger.debug("Created backup metadata: %s", meta_path)

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

        Also restores WAL and SHM files if they were backed up.

        Args:
            backup_path: Path to the backup file
            db_path: Path where the database should be restored

        Returns:
            True if restoration succeeded, False otherwise
        """
        try:
            shutil.copy2(backup_path, db_path)

            # Also restore WAL and SHM files if they exist in backup
            wal_backup = Path(str(backup_path) + "-wal")
            shm_backup = Path(str(backup_path) + "-shm")
            wal_target = Path(str(db_path) + "-wal")
            shm_target = Path(str(db_path) + "-shm")

            if wal_backup.exists():
                shutil.copy2(wal_backup, wal_target)
                logger.debug("Restored WAL file: %s", wal_target)
            elif wal_target.exists():
                # No WAL backup but target exists - remove stale WAL
                wal_target.unlink()
                logger.debug("Removed stale WAL file: %s", wal_target)

            if shm_backup.exists():
                shutil.copy2(shm_backup, shm_target)
                logger.debug("Restored SHM file: %s", shm_target)
            elif shm_target.exists():
                # No SHM backup but target exists - remove stale SHM
                shm_target.unlink()
                logger.debug("Removed stale SHM file: %s", shm_target)

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

    def get_original_path(self, backup_path: Path) -> Path | None:
        """
        Get the original database path from a backup's metadata.

        Args:
            backup_path: Path to the backup file

        Returns:
            Original database path if metadata exists, None otherwise
        """
        meta_path = Path(str(backup_path) + ".meta")

        if not meta_path.exists():
            logger.debug("No metadata file for backup: %s", backup_path)
            return None

        try:
            metadata = json.loads(meta_path.read_text())
            original_path = metadata.get("original_db_path")
            if original_path:
                return Path(original_path)
            return None
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning("Failed to read backup metadata %s: %s", meta_path, e)
            return None

    def get_backup_metadata(self, backup_path: Path) -> dict | None:
        """
        Get full metadata for a backup.

        Args:
            backup_path: Path to the backup file

        Returns:
            Metadata dict if available, None otherwise
        """
        meta_path = Path(str(backup_path) + ".meta")

        if not meta_path.exists():
            return None

        try:
            return json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read backup metadata %s: %s", meta_path, e)
            return None

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
                        # Delete associated files (meta, wal, shm)
                        for suffix in ["-wal", "-shm", ".meta"]:
                            associated = Path(str(backup_file) + suffix)
                            if associated.exists():
                                associated.unlink()
                                logger.debug("Deleted associated file: %s", associated)

                        # Delete the backup file itself
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
