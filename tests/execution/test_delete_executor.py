"""Tests for DeleteExecutor."""

import shutil
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.models import DeletePlan, DeleteOperation, DeleteTarget
from src.execution.delete_executor import DeleteExecutor, DeleteResult, DeleteReport
from src.execution.lock_resolver import LockResolver, LockReport
from src.execution.backup_manager import BackupManager, BackupResult


class TestDeleteResult:
    """Tests for DeleteResult dataclass."""

    def test_successful_result(self):
        """DeleteResult represents successful deletion."""
        result = DeleteResult(
            browser="Chrome",
            profile="Default",
            deleted_count=10,
            success=True,
        )
        assert result.success is True
        assert result.deleted_count == 10
        assert result.error is None

    def test_failed_result(self):
        """DeleteResult represents failed deletion."""
        result = DeleteResult(
            browser="Chrome",
            profile="Default",
            deleted_count=0,
            success=False,
            error="Database locked",
        )
        assert result.success is False
        assert result.error == "Database locked"


class TestDeleteReport:
    """Tests for DeleteReport dataclass."""

    def test_success_property_all_succeeded(self):
        """success returns True when all operations succeeded."""
        report = DeleteReport(
            plan_id="test-plan",
            dry_run=False,
            results=[
                DeleteResult(browser="Chrome", profile="Default", deleted_count=5, success=True),
                DeleteResult(browser="Firefox", profile="default", deleted_count=3, success=True),
            ],
            total_deleted=8,
            total_failed=0,
        )
        assert report.success is True

    def test_success_property_some_failed(self):
        """success returns False when some operations failed."""
        report = DeleteReport(
            plan_id="test-plan",
            dry_run=False,
            results=[
                DeleteResult(browser="Chrome", profile="Default", deleted_count=5, success=True),
                DeleteResult(browser="Firefox", profile="default", deleted_count=0, success=False, error="Locked"),
            ],
            total_deleted=5,
            total_failed=1,
        )
        assert report.success is False


class TestDeleteExecutor:
    """Tests for DeleteExecutor class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        path = Path(tempfile.mkdtemp())
        yield path
        shutil.rmtree(path, ignore_errors=True)

    @pytest.fixture
    def chromium_db(self, temp_dir):
        """Create a Chromium-style cookie database."""
        db_path = temp_dir / "Cookies"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE cookies (
                host_key TEXT NOT NULL,
                name TEXT NOT NULL,
                value TEXT,
                path TEXT,
                expires_utc INTEGER,
                is_secure INTEGER,
                is_httponly INTEGER,
                last_access_utc INTEGER,
                has_expires INTEGER,
                is_persistent INTEGER,
                priority INTEGER,
                encrypted_value BLOB,
                samesite INTEGER,
                source_scheme INTEGER,
                source_port INTEGER,
                last_update_utc INTEGER
            )
        """)
        # Insert test cookies
        cookies = [
            (".google.com", "SID", "value1"),
            (".google.com", "HSID", "value2"),
            (".facebook.com", "c_user", "value3"),
            (".facebook.com", "xs", "value4"),
            (".example.com", "session", "value5"),
        ]
        for host, name, value in cookies:
            cursor.execute(
                "INSERT INTO cookies (host_key, name, value, path, is_secure, is_httponly) VALUES (?, ?, ?, '/', 1, 1)",
                (host, name, value)
            )
        conn.commit()
        conn.close()
        return db_path

    @pytest.fixture
    def firefox_db(self, temp_dir):
        """Create a Firefox-style cookie database."""
        db_path = temp_dir / "cookies.sqlite"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE moz_cookies (
                id INTEGER PRIMARY KEY,
                host TEXT NOT NULL,
                name TEXT NOT NULL,
                value TEXT,
                path TEXT,
                expiry INTEGER,
                isSecure INTEGER,
                isHttpOnly INTEGER,
                sameSite INTEGER,
                originAttributes TEXT
            )
        """)
        # Insert test cookies
        cookies = [
            (".google.com", "NID", "value1"),
            (".twitter.com", "auth_token", "value2"),
        ]
        for host, name, value in cookies:
            cursor.execute(
                "INSERT INTO moz_cookies (host, name, value, path, isSecure, isHttpOnly, sameSite, originAttributes) VALUES (?, ?, ?, '/', 1, 1, 0, '')",
                (host, name, value)
            )
        conn.commit()
        conn.close()
        return db_path

    @pytest.fixture
    def mock_lock_resolver(self):
        """Create a mock LockResolver that reports files as unlocked."""
        resolver = MagicMock(spec=LockResolver)
        resolver.check_lock.return_value = LockReport(
            db_path=Path("/test"), is_locked=False
        )
        return resolver

    @pytest.fixture
    def backup_manager(self, temp_dir):
        """Create a BackupManager with temporary root."""
        return BackupManager(backup_root=temp_dir / "backups")

    @pytest.fixture
    def executor(self, mock_lock_resolver, backup_manager):
        """Create a DeleteExecutor with mocked dependencies."""
        return DeleteExecutor(
            lock_resolver=mock_lock_resolver,
            backup_manager=backup_manager,
        )

    def test_dry_run_no_modifications(self, executor, chromium_db, temp_dir):
        """Dry run does not modify database or create backups."""
        plan = DeletePlan.create(dry_run=True)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chromium_db,
            backup_path=temp_dir / "backup.bak",
            targets=[DeleteTarget(
                normalized_domain="google.com",
                match_pattern="%.google.com",
                count=2,
            )],
        ))

        report = executor.execute(plan, dry_run=True)

        assert report.dry_run is True
        assert len(report.results) == 1
        assert report.results[0].success is True

        # Verify no backup created
        assert not (temp_dir / "backups").exists() or not list((temp_dir / "backups").rglob("*.bak"))

        # Verify cookies still exist
        conn = sqlite3.connect(str(chromium_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%.google.com'")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 2

    def test_dry_run_reports_would_delete_not_deleted(self, executor, chromium_db, temp_dir):
        """Dry run reports would_delete_count > 0 and deleted_count = 0."""
        plan = DeletePlan.create(dry_run=True)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chromium_db,
            backup_path=temp_dir / "backup.bak",
            targets=[DeleteTarget(
                normalized_domain="google.com",
                match_pattern="%.google.com",
                count=2,
            )],
        ))

        report = executor.execute(plan, dry_run=True)

        # Dry run should report:
        # - deleted_count = 0 (nothing actually deleted)
        # - would_delete_count = actual count that would be deleted
        assert report.results[0].deleted_count == 0
        assert report.results[0].would_delete_count == 2
        assert report.total_deleted == 0
        assert report.total_would_delete == 2

    def test_successful_deletion_chromium(self, executor, chromium_db, temp_dir, backup_manager):
        """Successful deletion removes cookies and creates backup."""
        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chromium_db,
            backup_path=temp_dir / "backup.bak",
            targets=[DeleteTarget(
                normalized_domain="google.com",
                match_pattern="%.google.com",
                count=2,
            )],
        ))

        report = executor.execute(plan, dry_run=False)

        assert report.success is True
        assert report.total_deleted == 2
        assert report.results[0].backup_path is not None
        assert report.results[0].backup_path.exists()

        # Verify cookies deleted
        conn = sqlite3.connect(str(chromium_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%.google.com'")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0

        # Verify other cookies still exist
        conn = sqlite3.connect(str(chromium_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cookies")
        total = cursor.fetchone()[0]
        conn.close()
        assert total == 3  # facebook (2) + example (1)

    def test_successful_deletion_firefox(self, mock_lock_resolver, backup_manager, firefox_db, temp_dir):
        """Successful deletion works with Firefox database."""
        executor = DeleteExecutor(
            lock_resolver=mock_lock_resolver,
            backup_manager=backup_manager,
        )

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Firefox",
            profile="default-release",
            db_path=firefox_db,
            backup_path=temp_dir / "backup.bak",
            targets=[DeleteTarget(
                normalized_domain="google.com",
                match_pattern="%.google.com",
                count=1,
            )],
        ))

        report = executor.execute(plan, dry_run=False)

        assert report.success is True
        assert report.total_deleted == 1

        # Verify cookie deleted
        conn = sqlite3.connect(str(firefox_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM moz_cookies WHERE host LIKE '%.google.com'")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0

    def test_abort_when_database_locked(self, backup_manager, chromium_db, temp_dir):
        """Deletion aborts when database is locked."""
        mock_resolver = MagicMock(spec=LockResolver)
        mock_resolver.check_lock.return_value = LockReport(
            db_path=chromium_db,
            is_locked=True,
            error_code=32,
            blocking_processes=["chrome.exe"],
        )

        executor = DeleteExecutor(
            lock_resolver=mock_resolver,
            backup_manager=backup_manager,
        )

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chromium_db,
            backup_path=temp_dir / "backup.bak",
            targets=[DeleteTarget(
                normalized_domain="google.com",
                match_pattern="%.google.com",
                count=2,
            )],
        ))

        report = executor.execute(plan, dry_run=False)

        assert report.success is False
        assert report.total_failed == 1
        assert "locked" in report.results[0].error.lower()
        assert "chrome.exe" in report.results[0].error

        # Verify no cookies deleted
        conn = sqlite3.connect(str(chromium_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cookies")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 5  # All cookies still there

    def test_abort_when_backup_fails(self, mock_lock_resolver, chromium_db, temp_dir):
        """Deletion aborts when backup creation fails."""
        mock_backup = MagicMock(spec=BackupManager)
        mock_backup.create_backup.return_value = BackupResult(
            db_path=chromium_db,
            backup_path=temp_dir / "backup.bak",
            success=False,
            error="Permission denied",
        )

        executor = DeleteExecutor(
            lock_resolver=mock_lock_resolver,
            backup_manager=mock_backup,
        )

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chromium_db,
            backup_path=temp_dir / "backup.bak",
            targets=[DeleteTarget(
                normalized_domain="google.com",
                match_pattern="%.google.com",
                count=2,
            )],
        ))

        report = executor.execute(plan, dry_run=False)

        assert report.success is False
        assert "Backup failed" in report.results[0].error

        # Verify no cookies deleted
        conn = sqlite3.connect(str(chromium_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cookies")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 5

    def test_transaction_rollback_on_error(self, mock_lock_resolver, backup_manager, temp_dir):
        """Transaction is rolled back on SQL error."""
        # Create a corrupted database
        db_path = temp_dir / "Cookies"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE cookies (host_key TEXT)")
        # Don't add the required columns to cause an error
        conn.commit()
        conn.close()

        executor = DeleteExecutor(
            lock_resolver=mock_lock_resolver,
            backup_manager=backup_manager,
        )

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=db_path,
            backup_path=temp_dir / "backup.bak",
            targets=[DeleteTarget(
                normalized_domain="test.com",
                match_pattern="%.test.com",
                count=1,
            )],
        ))

        # This should succeed (DELETE on empty table)
        report = executor.execute(plan, dry_run=False)
        assert report.success is True

    def test_multiple_operations(self, mock_lock_resolver, backup_manager, chromium_db, firefox_db, temp_dir):
        """Executor handles multiple operations in one plan."""
        executor = DeleteExecutor(
            lock_resolver=mock_lock_resolver,
            backup_manager=backup_manager,
        )

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chromium_db,
            backup_path=temp_dir / "backup1.bak",
            targets=[DeleteTarget(
                normalized_domain="google.com",
                match_pattern="%.google.com",
                count=2,
            )],
        ))
        plan.add_operation(DeleteOperation(
            browser="Firefox",
            profile="default",
            db_path=firefox_db,
            backup_path=temp_dir / "backup2.bak",
            targets=[DeleteTarget(
                normalized_domain="twitter.com",
                match_pattern="%.twitter.com",
                count=1,
            )],
        ))

        report = executor.execute(plan, dry_run=False)

        assert report.success is True
        assert len(report.results) == 2
        assert report.total_deleted == 3  # 2 from Chrome + 1 from Firefox

    def test_multiple_targets_in_operation(self, executor, chromium_db, temp_dir):
        """Single operation can have multiple targets."""
        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chromium_db,
            backup_path=temp_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="google.com",
                    match_pattern="%.google.com",
                    count=2,
                ),
                DeleteTarget(
                    normalized_domain="facebook.com",
                    match_pattern="%.facebook.com",
                    count=2,
                ),
            ],
        ))

        report = executor.execute(plan, dry_run=False)

        assert report.success is True
        assert report.total_deleted == 4  # 2 google + 2 facebook

        # Verify only example.com cookies remain
        conn = sqlite3.connect(str(chromium_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cookies")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1

    def test_is_chromium_db_detection(self, executor, chromium_db, firefox_db):
        """_is_chromium_db correctly identifies database types."""
        assert executor._is_chromium_db(chromium_db) is True
        assert executor._is_chromium_db(firefox_db) is False

    def test_is_chromium_db_path_inference(self, executor):
        """_is_chromium_db infers type from path when database doesn't exist."""
        chrome_path = Path("C:/Users/test/AppData/Local/Google/Chrome/User Data/Default/Cookies")
        firefox_path = Path("C:/Users/test/AppData/Roaming/Mozilla/Firefox/Profiles/abc/cookies.sqlite")

        assert executor._is_chromium_db(chrome_path) is True
        assert executor._is_chromium_db(firefox_path) is False


class TestSQLPatterns:
    """Tests for SQL pattern generation."""

    @pytest.fixture
    def executor(self):
        """Create a DeleteExecutor with default dependencies."""
        return DeleteExecutor()

    def test_chromium_delete_sql(self, executor):
        """Chromium DELETE uses host_key column."""
        target = DeleteTarget(
            normalized_domain="example.com",
            match_pattern="%.example.com",
            count=1,
        )
        sql = executor._build_delete_sql(target, is_chromium=True)
        assert "cookies" in sql.lower()
        assert "host_key" in sql.lower()
        assert "LIKE" in sql.upper()

    def test_firefox_delete_sql(self, executor):
        """Firefox DELETE uses host column."""
        target = DeleteTarget(
            normalized_domain="example.com",
            match_pattern="%.example.com",
            count=1,
        )
        sql = executor._build_delete_sql(target, is_chromium=False)
        assert "moz_cookies" in sql.lower()
        assert "host" in sql.lower()
        assert "LIKE" in sql.upper()

    def test_chromium_count_sql(self, executor):
        """Chromium COUNT uses host_key column."""
        target = DeleteTarget(
            normalized_domain="example.com",
            match_pattern="%.example.com",
            count=1,
        )
        sql = executor._build_count_sql(target, is_chromium=True)
        assert "SELECT COUNT" in sql.upper()
        assert "host_key" in sql.lower()

    def test_firefox_count_sql(self, executor):
        """Firefox COUNT uses host column."""
        target = DeleteTarget(
            normalized_domain="example.com",
            match_pattern="%.example.com",
            count=1,
        )
        sql = executor._build_count_sql(target, is_chromium=False)
        assert "SELECT COUNT" in sql.upper()
        assert "moz_cookies" in sql.lower()
