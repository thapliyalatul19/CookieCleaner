"""Tests for database copy utility."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.scanner.db_copy import copy_db_to_temp, cleanup_temp_db


class TestCopyDbToTemp:
    """Tests for copy_db_to_temp function."""

    def test_copies_database_file(self, tmp_path: Path) -> None:
        """copy_db_to_temp copies the database file."""
        db_path = tmp_path / "Cookies"
        db_path.write_bytes(b"database content")

        temp_path = copy_db_to_temp(db_path)

        try:
            assert temp_path.exists()
            assert temp_path.read_bytes() == b"database content"
        finally:
            cleanup_temp_db(temp_path)

    def test_copies_wal_file(self, tmp_path: Path) -> None:
        """copy_db_to_temp copies WAL file if it exists."""
        db_path = tmp_path / "Cookies"
        db_path.write_bytes(b"database content")
        wal_path = tmp_path / "Cookies-wal"
        wal_path.write_bytes(b"wal content")

        temp_path = copy_db_to_temp(db_path)

        try:
            temp_wal = Path(str(temp_path) + "-wal")
            assert temp_wal.exists()
            assert temp_wal.read_bytes() == b"wal content"
        finally:
            cleanup_temp_db(temp_path)

    def test_copies_shm_file(self, tmp_path: Path) -> None:
        """copy_db_to_temp copies SHM file if it exists."""
        db_path = tmp_path / "Cookies"
        db_path.write_bytes(b"database content")
        shm_path = tmp_path / "Cookies-shm"
        shm_path.write_bytes(b"shm content")

        temp_path = copy_db_to_temp(db_path)

        try:
            temp_shm = Path(str(temp_path) + "-shm")
            assert temp_shm.exists()
            assert temp_shm.read_bytes() == b"shm content"
        finally:
            cleanup_temp_db(temp_path)

    def test_handles_missing_wal_shm(self, tmp_path: Path) -> None:
        """copy_db_to_temp succeeds when WAL/SHM don't exist."""
        db_path = tmp_path / "Cookies"
        db_path.write_bytes(b"database content")

        temp_path = copy_db_to_temp(db_path)

        try:
            assert temp_path.exists()
            temp_wal = Path(str(temp_path) + "-wal")
            temp_shm = Path(str(temp_path) + "-shm")
            assert not temp_wal.exists()
            assert not temp_shm.exists()
        finally:
            cleanup_temp_db(temp_path)

    def test_raises_for_nonexistent_db(self, tmp_path: Path) -> None:
        """copy_db_to_temp raises FileNotFoundError for missing db."""
        db_path = tmp_path / "Nonexistent"

        with pytest.raises(FileNotFoundError):
            copy_db_to_temp(db_path)


class TestCleanupTempDb:
    """Tests for cleanup_temp_db function."""

    def test_removes_database_file(self, tmp_path: Path) -> None:
        """cleanup_temp_db removes the database file."""
        temp_path = tmp_path / "temp.db"
        temp_path.write_bytes(b"content")

        cleanup_temp_db(temp_path)

        assert not temp_path.exists()

    def test_removes_wal_file(self, tmp_path: Path) -> None:
        """cleanup_temp_db removes WAL file if it exists."""
        temp_path = tmp_path / "temp.db"
        temp_path.write_bytes(b"content")
        wal_path = tmp_path / "temp.db-wal"
        wal_path.write_bytes(b"wal content")

        cleanup_temp_db(temp_path)

        assert not temp_path.exists()
        assert not wal_path.exists()

    def test_removes_shm_file(self, tmp_path: Path) -> None:
        """cleanup_temp_db removes SHM file if it exists."""
        temp_path = tmp_path / "temp.db"
        temp_path.write_bytes(b"content")
        shm_path = tmp_path / "temp.db-shm"
        shm_path.write_bytes(b"shm content")

        cleanup_temp_db(temp_path)

        assert not temp_path.exists()
        assert not shm_path.exists()

    def test_handles_missing_wal_shm(self, tmp_path: Path) -> None:
        """cleanup_temp_db succeeds when WAL/SHM don't exist."""
        temp_path = tmp_path / "temp.db"
        temp_path.write_bytes(b"content")

        # Should not raise
        cleanup_temp_db(temp_path)

        assert not temp_path.exists()

    def test_handles_nonexistent_file(self, tmp_path: Path) -> None:
        """cleanup_temp_db handles nonexistent file gracefully."""
        temp_path = tmp_path / "nonexistent.db"

        # Should not raise
        cleanup_temp_db(temp_path)

    def test_removes_all_files_atomically(self, tmp_path: Path) -> None:
        """cleanup_temp_db removes db, wal, and shm together."""
        temp_path = tmp_path / "temp.db"
        temp_path.write_bytes(b"db content")
        wal_path = tmp_path / "temp.db-wal"
        wal_path.write_bytes(b"wal content")
        shm_path = tmp_path / "temp.db-shm"
        shm_path.write_bytes(b"shm content")

        cleanup_temp_db(temp_path)

        assert not temp_path.exists()
        assert not wal_path.exists()
        assert not shm_path.exists()
