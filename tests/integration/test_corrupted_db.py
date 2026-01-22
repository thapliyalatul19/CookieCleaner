"""Integration tests for corrupted/empty database handling (Fixture E).

Tests graceful handling of:
- Empty databases (table exists, no rows)
- Corrupted/invalid files
- Missing tables
- Missing files
"""

from pathlib import Path

import pytest

from src.core.models import BrowserStore, DeleteOperation, DeletePlan, DeleteTarget
from src.execution.backup_manager import BackupManager
from src.execution.delete_executor import DeleteExecutor
from src.scanner.chromium_cookie_reader import ChromiumCookieReader
from src.scanner.firefox_cookie_reader import FirefoxCookieReader


class TestEmptyDatabase:
    """Test handling of empty databases."""

    def test_empty_chromium_db_returns_no_cookies(
        self, fixture_e_edge_cases: dict[str, Path]
    ):
        """Verify empty database returns empty list, no errors."""
        empty_path = fixture_e_edge_cases["empty"]

        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Empty",
            db_path=empty_path,
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        assert cookies == []

    def test_delete_on_empty_db_succeeds(
        self,
        fixture_e_edge_cases: dict[str, Path],
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Verify delete operation on empty DB succeeds with 0 deletions."""
        empty_path = fixture_e_edge_cases["empty"]

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Empty",
            db_path=empty_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget("example.com", "%.example.com", 0),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan)

        # Should succeed with 0 deletions
        assert report.success
        assert report.total_deleted == 0


class TestCorruptedDatabase:
    """Test handling of corrupted database files."""

    def test_corrupted_db_returns_no_cookies(
        self, fixture_e_edge_cases: dict[str, Path]
    ):
        """Verify corrupted database returns empty list gracefully."""
        corrupted_path = fixture_e_edge_cases["corrupted"]

        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Corrupted",
            db_path=corrupted_path,
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)

        # Should not raise an exception
        cookies = reader.read_cookies()

        # Should return empty list
        assert cookies == []

    def test_delete_on_corrupted_db_fails_gracefully(
        self,
        fixture_e_edge_cases: dict[str, Path],
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Verify delete on corrupted DB fails but doesn't crash."""
        corrupted_path = fixture_e_edge_cases["corrupted"]

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Corrupted",
            db_path=corrupted_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget("example.com", "%.example.com", 5),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )

        # Should not crash
        report = executor.execute(plan)

        # Operation should fail (database is not valid SQLite)
        assert not report.success or report.total_deleted == 0


class TestMissingTable:
    """Test handling of databases without cookies table."""

    def test_missing_table_returns_no_cookies(
        self, fixture_e_edge_cases: dict[str, Path]
    ):
        """Verify database without cookies table returns empty list."""
        missing_table_path = fixture_e_edge_cases["missing_table"]

        store = BrowserStore(
            browser_name="Chrome",
            profile_id="MissingTable",
            db_path=missing_table_path,
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        assert cookies == []

    def test_delete_on_missing_table_fails_gracefully(
        self,
        fixture_e_edge_cases: dict[str, Path],
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Verify delete on DB without cookies table fails gracefully."""
        missing_table_path = fixture_e_edge_cases["missing_table"]

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="MissingTable",
            db_path=missing_table_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget("example.com", "%.example.com", 5),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )

        # Should not crash
        report = executor.execute(plan)

        # Should fail because table doesn't exist
        assert not report.success or report.total_deleted == 0


class TestMissingFile:
    """Test handling of missing database files."""

    def test_missing_file_returns_no_cookies(
        self, fixture_e_edge_cases: dict[str, Path]
    ):
        """Verify missing file returns empty list."""
        missing_file_path = fixture_e_edge_cases["missing_file"]

        assert not missing_file_path.exists()

        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Missing",
            db_path=missing_file_path,
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        assert cookies == []

    def test_backup_missing_file_fails(
        self, fixture_e_edge_cases: dict[str, Path], temp_backup_dir: Path
    ):
        """Verify backup of missing file fails gracefully."""
        missing_file_path = fixture_e_edge_cases["missing_file"]

        backup_manager = BackupManager(temp_backup_dir)
        result = backup_manager.create_backup(
            missing_file_path, "Chrome", "Missing"
        )

        assert not result.success
        assert "not found" in result.error.lower()


class TestFirefoxEdgeCases:
    """Test Firefox-specific edge cases."""

    def test_firefox_missing_cookies_sqlite(
        self, integration_temp_dir: Path, golden_factory
    ):
        """Test Firefox profile without cookies.sqlite."""
        # Create profile directory without cookies.sqlite
        profile_path = integration_temp_dir / "firefox" / "empty_profile"
        profile_path.mkdir(parents=True)
        missing_path = profile_path / "cookies.sqlite"

        store = BrowserStore(
            browser_name="Firefox",
            profile_id="empty_profile",
            db_path=missing_path,
            is_chromium=False,
        )
        reader = FirefoxCookieReader(store)
        cookies = reader.read_cookies()

        assert cookies == []

    def test_firefox_wrong_table_structure(
        self, integration_temp_dir: Path
    ):
        """Test Firefox database with wrong table structure."""
        import sqlite3

        db_path = integration_temp_dir / "wrong_firefox" / "cookies.sqlite"
        db_path.parent.mkdir(parents=True)

        # Create SQLite with wrong table name
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE wrong_table (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        store = BrowserStore(
            browser_name="Firefox",
            profile_id="wrong",
            db_path=db_path,
            is_chromium=False,
        )
        reader = FirefoxCookieReader(store)
        cookies = reader.read_cookies()

        assert cookies == []


class TestIteratorBehavior:
    """Test iterator behavior with edge cases."""

    def test_iter_cookies_on_empty_db(
        self, fixture_e_edge_cases: dict[str, Path]
    ):
        """Verify iter_cookies works on empty database."""
        empty_path = fixture_e_edge_cases["empty"]

        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Empty",
            db_path=empty_path,
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)

        # Should be able to iterate (yields nothing)
        cookie_count = sum(1 for _ in reader.iter_cookies())
        assert cookie_count == 0

    def test_iter_cookies_on_corrupted_db(
        self, fixture_e_edge_cases: dict[str, Path]
    ):
        """Verify iter_cookies handles corrupted database."""
        corrupted_path = fixture_e_edge_cases["corrupted"]

        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Corrupted",
            db_path=corrupted_path,
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)

        # Should not raise, should yield nothing
        cookie_count = sum(1 for _ in reader.iter_cookies())
        assert cookie_count == 0

    def test_iter_cookies_on_missing_file(
        self, fixture_e_edge_cases: dict[str, Path]
    ):
        """Verify iter_cookies handles missing file."""
        missing_path = fixture_e_edge_cases["missing_file"]

        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Missing",
            db_path=missing_path,
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)

        # Should not raise, should yield nothing
        cookie_count = sum(1 for _ in reader.iter_cookies())
        assert cookie_count == 0


class TestSchemaVariations:
    """Test handling of schema variations."""

    def test_chromium_20_column_schema(
        self, integration_temp_dir: Path, golden_factory
    ):
        """Test standard Chrome 20-column schema."""
        db_path = integration_temp_dir / "chrome20" / "Cookies"
        db_path.parent.mkdir(parents=True)

        golden_factory.create_chromium_db(db_path, [
            (".example.com", "test", None, 1),
        ], schema_columns=20)

        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Default",
            db_path=db_path,
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        assert len(cookies) == 1
        assert cookies[0].domain == "example.com"

    def test_edge_22_column_schema(
        self, integration_temp_dir: Path, golden_factory
    ):
        """Test Edge 22-column schema (has extra columns)."""
        db_path = integration_temp_dir / "edge22" / "Cookies"
        db_path.parent.mkdir(parents=True)

        golden_factory.create_chromium_db(db_path, [
            (".microsoft.com", "muid", None, 1),
            (".bing.com", "search", None, 0),
        ], schema_columns=22)

        store = BrowserStore(
            browser_name="Edge",
            profile_id="Default",
            db_path=db_path,
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        assert len(cookies) == 2
        domains = {c.domain for c in cookies}
        assert "microsoft.com" in domains
        assert "bing.com" in domains
