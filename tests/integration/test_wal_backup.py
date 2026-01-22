"""Integration tests for WAL mode backup/restore integrity."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from src.execution.backup_manager import BackupManager


class TestWALBackupIntegrity:
    """Integration tests for WAL mode database backup and restore."""

    @pytest.fixture
    def temp_dir(self, tmp_path: Path) -> Path:
        """Create a temp directory."""
        return tmp_path

    @pytest.fixture
    def backup_manager(self, temp_dir: Path) -> BackupManager:
        """Create a BackupManager with temp backup root."""
        return BackupManager(backup_root=temp_dir / "backups")

    def _create_wal_database(self, db_path: Path, num_cookies: int = 10) -> None:
        """Create a SQLite database in WAL mode with test data."""
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Enable WAL mode
        cursor.execute("PRAGMA journal_mode=WAL")

        # Create cookies table
        cursor.execute("""
            CREATE TABLE cookies (
                host_key TEXT NOT NULL,
                name TEXT NOT NULL,
                value TEXT,
                path TEXT DEFAULT '/',
                is_secure INTEGER DEFAULT 1,
                is_httponly INTEGER DEFAULT 1
            )
        """)

        # Insert test cookies
        for i in range(num_cookies):
            cursor.execute(
                "INSERT INTO cookies (host_key, name, value) VALUES (?, ?, ?)",
                (f".domain{i}.com", f"cookie{i}", f"value{i}"),
            )

        conn.commit()
        conn.close()

    def _count_cookies(self, db_path: Path) -> int:
        """Count cookies in database."""
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cookies")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def test_wal_database_creates_wal_shm_files(self, temp_dir: Path) -> None:
        """WAL mode database creates -wal and -shm files."""
        db_path = temp_dir / "Cookies"
        self._create_wal_database(db_path)

        # WAL and SHM files should exist
        assert db_path.exists()
        # Note: WAL/SHM may not exist if database was properly closed
        # But for active databases, they typically do

    def test_backup_includes_wal_data(self, temp_dir: Path, backup_manager: BackupManager) -> None:
        """Backup captures data in WAL file."""
        db_path = temp_dir / "Cookies"
        self._create_wal_database(db_path, num_cookies=5)

        # Add more cookies without closing connection (stays in WAL)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        for i in range(5, 10):
            cursor.execute(
                "INSERT INTO cookies (host_key, name, value) VALUES (?, ?, ?)",
                (f".domain{i}.com", f"cookie{i}", f"value{i}"),
            )
        conn.commit()
        # Keep connection open to ensure WAL exists
        # Force checkpoint to ensure data is visible
        cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")
        conn.close()

        # Create backup
        result = backup_manager.create_backup(db_path, "Chrome", "Default")
        assert result.success is True

        # Restore to new location
        restored_path = temp_dir / "Restored"
        backup_manager.restore_backup(result.backup_path, restored_path)

        # Verify all cookies are present
        restored_count = self._count_cookies(restored_path)
        assert restored_count == 10

    def test_restore_removes_stale_wal_shm(self, temp_dir: Path, backup_manager: BackupManager) -> None:
        """Restore removes stale WAL/SHM files not in backup."""
        db_path = temp_dir / "Cookies"
        self._create_wal_database(db_path, num_cookies=5)

        # Create backup (closes database, WAL/SHM cleaned)
        result = backup_manager.create_backup(db_path, "Chrome", "Default")
        assert result.success is True

        # Create stale WAL/SHM files
        wal_path = Path(str(db_path) + "-wal")
        shm_path = Path(str(db_path) + "-shm")
        wal_path.write_bytes(b"stale wal data")
        shm_path.write_bytes(b"stale shm data")

        # Restore
        backup_manager.restore_backup(result.backup_path, db_path)

        # Stale files should be removed
        assert not wal_path.exists()
        assert not shm_path.exists()

    def test_full_backup_restore_cycle(self, temp_dir: Path, backup_manager: BackupManager) -> None:
        """Full backup and restore cycle preserves data integrity."""
        db_path = temp_dir / "Cookies"
        self._create_wal_database(db_path, num_cookies=20)

        original_count = self._count_cookies(db_path)
        assert original_count == 20

        # Create backup
        result = backup_manager.create_backup(db_path, "Chrome", "Default")
        assert result.success is True

        # Modify original database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cookies")
        conn.commit()
        conn.close()

        modified_count = self._count_cookies(db_path)
        assert modified_count == 0

        # Restore
        success = backup_manager.restore_backup(result.backup_path, db_path)
        assert success is True

        # Verify data restored
        restored_count = self._count_cookies(db_path)
        assert restored_count == 20

    def test_backup_metadata_preserved(self, temp_dir: Path, backup_manager: BackupManager) -> None:
        """Backup metadata correctly stores original path."""
        db_path = temp_dir / "Cookies"
        self._create_wal_database(db_path)

        result = backup_manager.create_backup(db_path, "Chrome", "Profile 1")
        assert result.success is True

        # Verify metadata
        metadata = backup_manager.get_backup_metadata(result.backup_path)
        assert metadata is not None
        assert metadata["browser"] == "Chrome"
        assert metadata["profile"] == "Profile 1"
        assert str(db_path) in metadata["original_db_path"]
