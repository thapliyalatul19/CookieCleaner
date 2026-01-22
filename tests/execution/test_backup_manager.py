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

    def test_create_backup_includes_wal_file(self, backup_manager, temp_dir):
        """create_backup backs up WAL file if it exists."""
        # Create db with WAL file
        db_path = temp_dir / "Cookies"
        db_path.write_bytes(b"database content")
        wal_path = temp_dir / "Cookies-wal"
        wal_path.write_bytes(b"wal content")

        result = backup_manager.create_backup(db_path, "Chrome", "Default")

        assert result.success is True
        wal_backup = Path(str(result.backup_path) + "-wal")
        assert wal_backup.exists()
        assert wal_backup.read_bytes() == b"wal content"

    def test_create_backup_includes_shm_file(self, backup_manager, temp_dir):
        """create_backup backs up SHM file if it exists."""
        # Create db with SHM file
        db_path = temp_dir / "Cookies"
        db_path.write_bytes(b"database content")
        shm_path = temp_dir / "Cookies-shm"
        shm_path.write_bytes(b"shm content")

        result = backup_manager.create_backup(db_path, "Chrome", "Default")

        assert result.success is True
        shm_backup = Path(str(result.backup_path) + "-shm")
        assert shm_backup.exists()
        assert shm_backup.read_bytes() == b"shm content"

    def test_create_backup_handles_missing_wal_shm(self, backup_manager, temp_dir):
        """create_backup succeeds when WAL/SHM don't exist."""
        db_path = temp_dir / "Cookies"
        db_path.write_bytes(b"database content")

        result = backup_manager.create_backup(db_path, "Chrome", "Default")

        assert result.success is True
        wal_backup = Path(str(result.backup_path) + "-wal")
        shm_backup = Path(str(result.backup_path) + "-shm")
        assert not wal_backup.exists()
        assert not shm_backup.exists()

    def test_restore_backup_includes_wal_file(self, backup_manager, temp_dir):
        """restore_backup restores WAL file if it was backed up."""
        # Create db with WAL file
        db_path = temp_dir / "Cookies"
        db_path.write_bytes(b"database content")
        wal_path = temp_dir / "Cookies-wal"
        wal_path.write_bytes(b"wal content")

        # Create backup
        result = backup_manager.create_backup(db_path, "Chrome", "Default")
        assert result.success is True

        # Modify originals
        db_path.write_bytes(b"modified")
        wal_path.write_bytes(b"modified wal")

        # Restore
        success = backup_manager.restore_backup(result.backup_path, db_path)

        assert success is True
        assert db_path.read_bytes() == b"database content"
        assert wal_path.read_bytes() == b"wal content"

    def test_restore_backup_includes_shm_file(self, backup_manager, temp_dir):
        """restore_backup restores SHM file if it was backed up."""
        # Create db with SHM file
        db_path = temp_dir / "Cookies"
        db_path.write_bytes(b"database content")
        shm_path = temp_dir / "Cookies-shm"
        shm_path.write_bytes(b"shm content")

        # Create backup
        result = backup_manager.create_backup(db_path, "Chrome", "Default")
        assert result.success is True

        # Modify originals
        db_path.write_bytes(b"modified")
        shm_path.write_bytes(b"modified shm")

        # Restore
        success = backup_manager.restore_backup(result.backup_path, db_path)

        assert success is True
        assert db_path.read_bytes() == b"database content"
        assert shm_path.read_bytes() == b"shm content"

    def test_restore_removes_stale_wal_shm(self, backup_manager, temp_dir):
        """restore_backup removes stale WAL/SHM files not in backup."""
        # Create db without WAL/SHM
        db_path = temp_dir / "Cookies"
        db_path.write_bytes(b"database content")

        # Create backup (no WAL/SHM)
        result = backup_manager.create_backup(db_path, "Chrome", "Default")
        assert result.success is True

        # Create WAL/SHM files (stale)
        wal_path = temp_dir / "Cookies-wal"
        shm_path = temp_dir / "Cookies-shm"
        wal_path.write_bytes(b"stale wal")
        shm_path.write_bytes(b"stale shm")

        # Restore - should remove stale files
        success = backup_manager.restore_backup(result.backup_path, db_path)

        assert success is True
        assert not wal_path.exists()
        assert not shm_path.exists()


class TestBackupMetadata:
    """Tests for backup metadata functionality."""

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

    def test_create_backup_writes_metadata_file(self, backup_manager, temp_db):
        """create_backup creates .meta file alongside backup."""
        result = backup_manager.create_backup(temp_db, "Chrome", "Default")

        assert result.success is True
        meta_path = Path(str(result.backup_path) + ".meta")
        assert meta_path.exists()

    def test_metadata_contains_original_path(self, backup_manager, temp_db):
        """Metadata file contains original database path."""
        import json

        result = backup_manager.create_backup(temp_db, "Chrome", "Default")
        meta_path = Path(str(result.backup_path) + ".meta")

        metadata = json.loads(meta_path.read_text())
        assert metadata["original_db_path"] == str(temp_db)

    def test_metadata_contains_browser_profile(self, backup_manager, temp_db):
        """Metadata file contains browser and profile info."""
        import json

        result = backup_manager.create_backup(temp_db, "Chrome", "Profile 1")
        meta_path = Path(str(result.backup_path) + ".meta")

        metadata = json.loads(meta_path.read_text())
        assert metadata["browser"] == "Chrome"
        assert metadata["profile"] == "Profile 1"

    def test_metadata_contains_timestamp(self, backup_manager, temp_db):
        """Metadata file contains creation timestamp."""
        import json

        result = backup_manager.create_backup(temp_db, "Chrome", "Default")
        meta_path = Path(str(result.backup_path) + ".meta")

        metadata = json.loads(meta_path.read_text())
        assert "timestamp" in metadata
        assert "created_at" in metadata

    def test_get_original_path_returns_path(self, backup_manager, temp_db):
        """get_original_path returns original path from metadata."""
        result = backup_manager.create_backup(temp_db, "Chrome", "Default")

        original = backup_manager.get_original_path(result.backup_path)

        assert original == temp_db

    def test_get_original_path_none_for_missing_metadata(self, backup_manager, temp_dir):
        """get_original_path returns None when metadata doesn't exist."""
        backup_path = temp_dir / "backup.bak"
        backup_path.write_bytes(b"content")

        original = backup_manager.get_original_path(backup_path)

        assert original is None

    def test_get_original_path_none_for_invalid_metadata(self, backup_manager, temp_dir):
        """get_original_path returns None for malformed metadata."""
        backup_path = temp_dir / "backup.bak"
        backup_path.write_bytes(b"content")
        meta_path = temp_dir / "backup.bak.meta"
        meta_path.write_text("not valid json")

        original = backup_manager.get_original_path(backup_path)

        assert original is None

    def test_get_backup_metadata_returns_full_metadata(self, backup_manager, temp_db):
        """get_backup_metadata returns complete metadata dict."""
        result = backup_manager.create_backup(temp_db, "Chrome", "Default")

        metadata = backup_manager.get_backup_metadata(result.backup_path)

        assert metadata is not None
        assert "original_db_path" in metadata
        assert "browser" in metadata
        assert "profile" in metadata
        assert "timestamp" in metadata
        assert "created_at" in metadata

    def test_get_backup_metadata_none_for_missing(self, backup_manager, temp_dir):
        """get_backup_metadata returns None when metadata doesn't exist."""
        backup_path = temp_dir / "backup.bak"
        backup_path.write_bytes(b"content")

        metadata = backup_manager.get_backup_metadata(backup_path)

        assert metadata is None
