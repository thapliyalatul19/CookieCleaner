"""Tests for BackupManager."""

import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.execution.backup_manager import BackupManager, BackupResult


class TestBackupResult:
    """Tests for BackupResult dataclass."""

    def test_success_result(self):
        """BackupResult with success=True has no error."""
        result = BackupResult(
            db_path=Path("/test/db"),
            backup_path=Path("/backup/db.bak"),
            success=True,
        )
        assert result.success is True
        assert result.error is None

    def test_failure_result(self):
        """BackupResult with success=False has error message."""
        result = BackupResult(
            db_path=Path("/test/db"),
            backup_path=Path("/backup/db.bak"),
            success=False,
            error="Permission denied",
        )
        assert result.success is False
        assert result.error == "Permission denied"


class TestBackupManager:
    """Tests for BackupManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        path = Path(tempfile.mkdtemp())
        yield path
        shutil.rmtree(path, ignore_errors=True)

    @pytest.fixture
    def backup_manager(self, temp_dir):
        """Create a BackupManager with temporary backup root."""
        return BackupManager(backup_root=temp_dir / "backups")

    @pytest.fixture
    def temp_db(self, temp_dir):
        """Create a temporary database file."""
        db_path = temp_dir / "Cookies"
        db_path.write_bytes(b"SQLite database content")
        return db_path

    def test_create_backup_success(self, backup_manager, temp_db):
        """create_backup creates backup file with correct path format."""
        result = backup_manager.create_backup(temp_db, "Chrome", "Default")

        assert result.success is True
        assert result.backup_path.exists()
        assert result.backup_path.parent.name == "Default"
        assert result.backup_path.parent.parent.name == "Chrome"
        assert ".bak" in result.backup_path.name
        assert "Cookies" in result.backup_path.name

    def test_create_backup_preserves_content(self, backup_manager, temp_db):
        """create_backup preserves file content."""
        original_content = temp_db.read_bytes()
        result = backup_manager.create_backup(temp_db, "Chrome", "Default")

        assert result.success is True
        backup_content = result.backup_path.read_bytes()
        assert backup_content == original_content

    def test_create_backup_timestamp_format(self, backup_manager, temp_db):
        """create_backup uses correct timestamp format in filename."""
        result = backup_manager.create_backup(temp_db, "Chrome", "Default")

        # Filename format: Cookies.20260120_143052.bak
        assert result.success is True
        parts = result.backup_path.name.split(".")
        assert len(parts) == 3  # Cookies, timestamp, bak
        timestamp = parts[1]
        # Verify timestamp is 15 chars: YYYYMMDD_HHMMSS
        assert len(timestamp) == 15
        assert timestamp[8] == "_"

    def test_create_backup_nonexistent_source(self, backup_manager):
        """create_backup fails gracefully for nonexistent source."""
        result = backup_manager.create_backup(
            Path("/nonexistent/path"), "Chrome", "Default"
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_create_backup_creates_directory_structure(self, backup_manager, temp_db):
        """create_backup creates nested directory structure."""
        result = backup_manager.create_backup(temp_db, "Edge", "Profile 1")

        assert result.success is True
        assert (backup_manager.backup_root / "Edge" / "Profile 1").is_dir()

    def test_restore_backup_success(self, backup_manager, temp_db, temp_dir):
        """restore_backup restores file content."""
        # Create backup
        result = backup_manager.create_backup(temp_db, "Chrome", "Default")
        assert result.success is True

        # Modify original
        temp_db.write_bytes(b"Modified content")

        # Restore
        success = backup_manager.restore_backup(result.backup_path, temp_db)

        assert success is True
        assert temp_db.read_bytes() == b"SQLite database content"

    def test_restore_backup_nonexistent_backup(self, backup_manager, temp_db):
        """restore_backup fails for nonexistent backup file."""
        success = backup_manager.restore_backup(
            Path("/nonexistent/backup.bak"), temp_db
        )
        assert success is False

    def test_get_latest_backup_returns_most_recent(self, backup_manager, temp_db):
        """get_latest_backup returns the most recent backup."""
        # Create multiple backups with small delays
        backup_manager.create_backup(temp_db, "Chrome", "Default")
        time.sleep(0.1)
        result2 = backup_manager.create_backup(temp_db, "Chrome", "Default")

        latest = backup_manager.get_latest_backup("Chrome", "Default")

        assert latest is not None
        assert latest == result2.backup_path

    def test_get_latest_backup_none_when_no_backups(self, backup_manager):
        """get_latest_backup returns None when no backups exist."""
        latest = backup_manager.get_latest_backup("Chrome", "Default")
        assert latest is None

    def test_get_latest_backup_none_for_wrong_browser(self, backup_manager, temp_db):
        """get_latest_backup returns None for different browser."""
        backup_manager.create_backup(temp_db, "Chrome", "Default")
        latest = backup_manager.get_latest_backup("Firefox", "Default")
        assert latest is None

    def test_list_backups_all(self, backup_manager, temp_db):
        """list_backups returns all backups without filters."""
        backup_manager.create_backup(temp_db, "Chrome", "Default")
        backup_manager.create_backup(temp_db, "Firefox", "default-release")

        backups = backup_manager.list_backups()
        assert len(backups) == 2

    def test_list_backups_by_browser(self, backup_manager, temp_db):
        """list_backups filters by browser."""
        backup_manager.create_backup(temp_db, "Chrome", "Default")
        backup_manager.create_backup(temp_db, "Firefox", "default-release")

        chrome_backups = backup_manager.list_backups(browser="Chrome")
        assert len(chrome_backups) == 1

    def test_list_backups_by_browser_and_profile(self, backup_manager, temp_db):
        """list_backups filters by browser and profile."""
        backup_manager.create_backup(temp_db, "Chrome", "Default")
        backup_manager.create_backup(temp_db, "Chrome", "Profile 1")

        default_backups = backup_manager.list_backups(browser="Chrome", profile="Default")
        assert len(default_backups) == 1

    def test_cleanup_old_backups_removes_old(self, backup_manager, temp_db, temp_dir):
        """cleanup_old_backups removes backups older than retention."""
        # Create a backup
        result = backup_manager.create_backup(temp_db, "Chrome", "Default")
        assert result.success is True

        # Manually set mtime to 10 days ago
        import os
        old_time = time.time() - (10 * 86400)
        os.utime(result.backup_path, (old_time, old_time))

        # Cleanup with 7-day retention
        deleted = backup_manager.cleanup_old_backups(retention_days=7)

        assert deleted == 1
        assert not result.backup_path.exists()

    def test_cleanup_old_backups_keeps_recent(self, backup_manager, temp_db):
        """cleanup_old_backups keeps recent backups."""
        result = backup_manager.create_backup(temp_db, "Chrome", "Default")
        assert result.success is True

        # Cleanup with 7-day retention (backup is fresh)
        deleted = backup_manager.cleanup_old_backups(retention_days=7)

        assert deleted == 0
        assert result.backup_path.exists()

    def test_cleanup_old_backups_invalid_retention(self, backup_manager):
        """cleanup_old_backups raises for negative retention."""
        with pytest.raises(ValueError, match="non-negative"):
            backup_manager.cleanup_old_backups(retention_days=-1)

    def test_cleanup_removes_empty_directories(self, backup_manager, temp_db):
        """cleanup_old_backups removes empty directories after deletion."""
        result = backup_manager.create_backup(temp_db, "Chrome", "Default")
        assert result.success is True

        # Make backup old
        import os
        old_time = time.time() - (10 * 86400)
        os.utime(result.backup_path, (old_time, old_time))

        # Cleanup
        backup_manager.cleanup_old_backups(retention_days=7)

        # Directory should be gone
        assert not (backup_manager.backup_root / "Chrome" / "Default").exists()
