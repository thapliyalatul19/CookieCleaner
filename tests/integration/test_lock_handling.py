"""Integration tests for process lock handling (Fixture C).

Tests the safety protocol when browser databases are locked:
- Detect locked databases
- Block deletion when locked
- Allow deletion after lock resolved
- Handle mixed locked/unlocked profiles
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.models import BrowserStore, DeleteOperation, DeletePlan, DeleteTarget
from src.execution.backup_manager import BackupManager
from src.execution.delete_executor import DeleteExecutor, DeleteReport
from src.execution.lock_resolver import LockResolver, LockReport

from .conftest import count_cookies_in_chromium_db


class TestLockDetection:
    """Test lock detection and blocking behavior."""

    def test_locked_database_blocks_deletion(
        self,
        fixture_c_multi_profile: dict[str, Path],
        fixture_c_stores: dict[str, BrowserStore],
        temp_backup_dir: Path,
        locked_lock_resolver: MagicMock,
    ):
        """
        Verify deletion is blocked when database is locked.

        PRD 12.1: Locked browser triggers "Close Browser" warning.
        """
        chrome_path = fixture_c_multi_profile["chrome_default"]
        initial_count = count_cookies_in_chromium_db(chrome_path)

        plan = DeletePlan.create(dry_run=False)
        operation = DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="google.com",
                    match_pattern="%.google.com",
                    count=1,
                ),
            ],
        )
        plan.add_operation(operation)

        # Use locked resolver
        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=locked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan)

        # Verify operation failed due to lock
        assert not report.success
        assert report.total_failed == 1
        assert report.total_deleted == 0

        # Verify error mentions lock
        assert len(report.results) == 1
        assert "locked" in report.results[0].error.lower()
        assert "chrome.exe" in report.results[0].error

        # Verify cookies unchanged
        final_count = count_cookies_in_chromium_db(chrome_path)
        assert final_count == initial_count

        # Verify no backup was created (lock detected before backup)
        backups = list(temp_backup_dir.rglob("*.bak"))
        assert len(backups) == 0

    def test_unlocked_database_allows_deletion(
        self,
        fixture_c_multi_profile: dict[str, Path],
        temp_backup_dir: Path,
        unlocked_lock_resolver: MagicMock,
    ):
        """Verify deletion proceeds when database is unlocked."""
        chrome_path = fixture_c_multi_profile["chrome_default"]
        initial_count = count_cookies_in_chromium_db(chrome_path)
        assert initial_count > 0

        plan = DeletePlan.create(dry_run=False)
        operation = DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="google.com",
                    match_pattern="%.google.com",
                    count=1,
                ),
            ],
        )
        plan.add_operation(operation)

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan)

        assert report.success
        assert report.total_deleted == 1

        # Verify backup was created
        backups = list(temp_backup_dir.rglob("*.bak"))
        assert len(backups) == 1


class TestMixedLockScenarios:
    """Test scenarios with some locked and some unlocked profiles."""

    def test_mixed_locked_unlocked_profiles(
        self,
        fixture_c_multi_profile: dict[str, Path],
        fixture_c_stores: dict[str, BrowserStore],
        temp_backup_dir: Path,
    ):
        """
        Test deletion across multiple profiles where some are locked.

        Scenario:
        - Chrome Default: unlocked -> deletion succeeds
        - Chrome Profile 1: unlocked -> deletion succeeds
        - Edge Default: locked -> deletion fails
        """
        chrome_default = fixture_c_multi_profile["chrome_default"]
        chrome_p1 = fixture_c_multi_profile["chrome_profile1"]
        edge_default = fixture_c_multi_profile["edge_default"]

        # Create mock resolver that returns different results per path
        mock_resolver = MagicMock(spec=LockResolver)

        def check_lock_side_effect(db_path):
            if "edge" in str(db_path).lower():
                return LockReport(db_path=db_path, is_locked=True, blocking_processes=["msedge.exe"])
            return LockReport(db_path=db_path, is_locked=False, blocking_processes=[])

        mock_resolver.check_lock.side_effect = check_lock_side_effect

        plan = DeletePlan.create(dry_run=False)

        # Add operations for all profiles
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_default,
            backup_path=temp_backup_dir / "chrome_default.bak",
            targets=[
                DeleteTarget("google.com", "%.google.com", 1),
            ],
        ))

        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Profile 1",
            db_path=chrome_p1,
            backup_path=temp_backup_dir / "chrome_p1.bak",
            targets=[
                DeleteTarget("google.com", "%.google.com", 1),
            ],
        ))

        plan.add_operation(DeleteOperation(
            browser="Edge",
            profile="Default",
            db_path=edge_default,
            backup_path=temp_backup_dir / "edge.bak",
            targets=[
                DeleteTarget("bing.com", "%.bing.com", 1),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=mock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan)

        # Report should show partial success
        assert not report.success  # One failure means overall not success
        assert report.total_deleted == 2  # Chrome profiles succeeded
        assert report.total_failed == 1  # Edge failed

        # Check individual results
        chrome_default_result = next(
            r for r in report.results if r.profile == "Default" and r.browser == "Chrome"
        )
        chrome_p1_result = next(r for r in report.results if r.profile == "Profile 1")
        edge_result = next(r for r in report.results if r.browser == "Edge")

        assert chrome_default_result.success
        assert chrome_p1_result.success
        assert not edge_result.success
        assert "msedge.exe" in edge_result.error

    def test_retry_after_lock_resolved(
        self,
        fixture_c_multi_profile: dict[str, Path],
        temp_backup_dir: Path,
    ):
        """
        Simulate user closing browser and retrying.

        First attempt: locked -> fail
        Second attempt: unlocked -> success
        """
        edge_path = fixture_c_multi_profile["edge_default"]
        initial_count = count_cookies_in_chromium_db(edge_path)

        # First attempt with lock
        locked_resolver = MagicMock(spec=LockResolver)
        locked_resolver.check_lock.return_value = LockReport(
            db_path=edge_path, is_locked=True, blocking_processes=["msedge.exe"]
        )

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Edge",
            profile="Default",
            db_path=edge_path,
            backup_path=temp_backup_dir / "edge.bak",
            targets=[
                DeleteTarget("bing.com", "%.bing.com", 1),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor1 = DeleteExecutor(
            lock_resolver=locked_resolver,
            backup_manager=backup_manager,
        )
        report1 = executor1.execute(plan)

        # First attempt fails
        assert not report1.success
        assert report1.total_failed == 1

        # Simulate user closing Edge (now unlocked)
        unlocked_resolver = MagicMock(spec=LockResolver)
        unlocked_resolver.check_lock.return_value = LockReport(
            db_path=edge_path, is_locked=False, blocking_processes=[]
        )

        # Create new plan for retry
        retry_plan = DeletePlan.create(dry_run=False)
        retry_plan.add_operation(DeleteOperation(
            browser="Edge",
            profile="Default",
            db_path=edge_path,
            backup_path=temp_backup_dir / "edge_retry.bak",
            targets=[
                DeleteTarget("bing.com", "%.bing.com", 1),
            ],
        ))

        executor2 = DeleteExecutor(
            lock_resolver=unlocked_resolver,
            backup_manager=backup_manager,
        )
        report2 = executor2.execute(retry_plan)

        # Second attempt succeeds
        assert report2.success
        assert report2.total_deleted == 1

        # Verify cookies actually deleted
        final_count = count_cookies_in_chromium_db(edge_path)
        assert final_count == initial_count - 1


class TestLockResolverIntegration:
    """Test actual LockResolver behavior (non-mocked)."""

    def test_real_lock_resolver_on_temp_db(
        self,
        fixture_c_multi_profile: dict[str, Path],
    ):
        """
        Test real LockResolver on a temporary database.

        Since we're using temp files, they shouldn't be locked.
        """
        chrome_path = fixture_c_multi_profile["chrome_default"]

        # Use real LockResolver
        resolver = LockResolver()
        lock_report = resolver.check_lock(chrome_path)

        # Temp file should not be locked
        assert not lock_report.is_locked
        assert lock_report.blocking_processes == []

    def test_lock_resolver_nonexistent_file(self):
        """Test LockResolver behavior with nonexistent file."""
        from pathlib import Path

        resolver = LockResolver()
        fake_path = Path("/nonexistent/path/Cookies")

        # Should not crash, should report not locked (file doesn't exist)
        lock_report = resolver.check_lock(fake_path)
        assert not lock_report.is_locked


class TestDryRunWithLocks:
    """Test dry run mode interaction with lock checks."""

    def test_dry_run_still_checks_locks(
        self,
        fixture_c_multi_profile: dict[str, Path],
        temp_backup_dir: Path,
        locked_lock_resolver: MagicMock,
    ):
        """
        Verify dry run still checks for locks.

        Even in dry run, we want to report if deletion would be blocked.
        """
        chrome_path = fixture_c_multi_profile["chrome_default"]

        plan = DeletePlan.create(dry_run=True)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget("google.com", "%.google.com", 1),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=locked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan, dry_run=True)

        # Dry run should still report lock failure
        assert not report.success
        assert "locked" in report.results[0].error.lower()

        # Verify lock check was called
        locked_lock_resolver.check_lock.assert_called_once()


class TestAbortAllPolicy:
    """Test that the abort-all policy is enforced.

    PRD requires that when ANY browser with cookies targeted for deletion is
    running, the ENTIRE operation should be aborted - no partial deletions.
    """

    def test_process_gate_aborts_entire_plan(
        self,
        fixture_c_multi_profile: dict[str, Path],
        temp_backup_dir: Path,
    ):
        """
        Verify process gate aborts entire plan when any browser is running.

        Even if only Chrome is running, and plan includes both Chrome and Edge,
        the process gate should abort the entire operation.
        """
        from src.execution.delete_executor import ProcessGateError

        chrome_default = fixture_c_multi_profile["chrome_default"]
        edge_default = fixture_c_multi_profile["edge_default"]

        # Mock resolver that shows Chrome is running
        mock_resolver = MagicMock(spec=LockResolver)
        mock_resolver.check_lock.return_value = LockReport(
            db_path=chrome_default, is_locked=False, blocking_processes=[]
        )
        # Simulate Chrome running
        mock_resolver.get_running_browsers.return_value = {"chrome.exe"}

        plan = DeletePlan.create(dry_run=False)

        # Add Chrome operation with browser_executable
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_default,
            backup_path=temp_backup_dir / "chrome.bak",
            browser_executable="chrome.exe",
            targets=[
                DeleteTarget("google.com", "%.google.com", 1),
            ],
        ))

        # Add Edge operation - Edge is NOT running
        plan.add_operation(DeleteOperation(
            browser="Edge",
            profile="Default",
            db_path=edge_default,
            backup_path=temp_backup_dir / "edge.bak",
            browser_executable="msedge.exe",
            targets=[
                DeleteTarget("bing.com", "%.bing.com", 1),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=mock_resolver,
            backup_manager=backup_manager,
        )

        # Should raise ProcessGateError, not partial execute
        with pytest.raises(ProcessGateError) as exc_info:
            executor.execute(plan)

        # Verify Chrome is in the blocking list
        assert "chrome.exe" in exc_info.value.running_browsers

        # Verify NO deletions occurred (abort-all, not partial)
        initial_chrome = count_cookies_in_chromium_db(chrome_default)
        initial_edge = count_cookies_in_chromium_db(edge_default)
        assert initial_chrome == 2  # google.com + facebook.com cookies
        assert initial_edge == 2  # bing.com + microsoft.com cookies

    def test_process_gate_allows_when_no_browsers_running(
        self,
        fixture_c_multi_profile: dict[str, Path],
        temp_backup_dir: Path,
    ):
        """
        Verify operations proceed when no blocking browsers are running.
        """
        chrome_default = fixture_c_multi_profile["chrome_default"]
        initial_count = count_cookies_in_chromium_db(chrome_default)

        # Mock resolver that shows no browsers running
        mock_resolver = MagicMock(spec=LockResolver)
        mock_resolver.check_lock.return_value = LockReport(
            db_path=chrome_default, is_locked=False, blocking_processes=[]
        )
        mock_resolver.get_running_browsers.return_value = set()

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_default,
            backup_path=temp_backup_dir / "chrome.bak",
            browser_executable="chrome.exe",
            targets=[
                DeleteTarget("google.com", "%.google.com", 1),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=mock_resolver,
            backup_manager=backup_manager,
        )

        # Should succeed without exception
        report = executor.execute(plan)

        assert report.success
        assert report.total_deleted == 1

        # Verify deletion occurred
        final_count = count_cookies_in_chromium_db(chrome_default)
        assert final_count == initial_count - 1

    def test_process_gate_only_checks_relevant_browsers(
        self,
        fixture_c_multi_profile: dict[str, Path],
        temp_backup_dir: Path,
    ):
        """
        Verify process gate only blocks browsers with operations in the plan.

        If Firefox is running but plan only targets Chrome, should proceed.
        """
        chrome_default = fixture_c_multi_profile["chrome_default"]
        initial_count = count_cookies_in_chromium_db(chrome_default)

        # Mock resolver that shows Firefox is running (but not Chrome)
        mock_resolver = MagicMock(spec=LockResolver)
        mock_resolver.check_lock.return_value = LockReport(
            db_path=chrome_default, is_locked=False, blocking_processes=[]
        )
        mock_resolver.get_running_browsers.return_value = {"firefox.exe"}

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_default,
            backup_path=temp_backup_dir / "chrome.bak",
            browser_executable="chrome.exe",  # Chrome, not Firefox
            targets=[
                DeleteTarget("google.com", "%.google.com", 1),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=mock_resolver,
            backup_manager=backup_manager,
        )

        # Should succeed - Firefox running doesn't affect Chrome operations
        report = executor.execute(plan)

        assert report.success
        assert report.total_deleted == 1

        # Verify deletion occurred
        final_count = count_cookies_in_chromium_db(chrome_default)
        assert final_count == initial_count - 1

    def test_multiple_browsers_running_lists_all_blockers(
        self,
        fixture_c_multi_profile: dict[str, Path],
        temp_backup_dir: Path,
    ):
        """
        Verify ProcessGateError lists all blocking browsers, not just one.
        """
        from src.execution.delete_executor import ProcessGateError

        chrome_default = fixture_c_multi_profile["chrome_default"]
        edge_default = fixture_c_multi_profile["edge_default"]

        # Mock resolver that shows both Chrome and Edge are running
        mock_resolver = MagicMock(spec=LockResolver)
        mock_resolver.get_running_browsers.return_value = {"chrome.exe", "msedge.exe"}

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_default,
            backup_path=temp_backup_dir / "chrome.bak",
            browser_executable="chrome.exe",
            targets=[DeleteTarget("google.com", "%.google.com", 1)],
        ))
        plan.add_operation(DeleteOperation(
            browser="Edge",
            profile="Default",
            db_path=edge_default,
            backup_path=temp_backup_dir / "edge.bak",
            browser_executable="msedge.exe",
            targets=[DeleteTarget("bing.com", "%.bing.com", 1)],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=mock_resolver,
            backup_manager=backup_manager,
        )

        with pytest.raises(ProcessGateError) as exc_info:
            executor.execute(plan)

        # Both browsers should be listed
        assert "chrome.exe" in exc_info.value.running_browsers
        assert "msedge.exe" in exc_info.value.running_browsers
