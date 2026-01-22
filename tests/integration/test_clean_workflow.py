"""Integration tests for full clean workflow.

Tests end-to-end deletion workflows:
- Full scan -> review -> clean cycle
- Backup creation and verification
- Audit log verification
- Post-clean counts
- Restore from backup
"""

from pathlib import Path
from datetime import datetime
import json

import pytest

from src.core.models import (
    BrowserStore, CookieRecord, DeleteOperation, DeletePlan, DeleteTarget,
    DomainAggregate,
)
from src.core.whitelist import WhitelistManager
from src.execution.backup_manager import BackupManager
from src.execution.delete_executor import DeleteExecutor
from src.scanner.chromium_cookie_reader import ChromiumCookieReader
from src.scanner.firefox_cookie_reader import FirefoxCookieReader
from src.scanner.cookie_reader import create_reader as create_cookie_reader

from .conftest import (
    count_cookies_in_chromium_db,
    count_cookies_in_firefox_db,
    count_cookies_by_domain_in_chromium_db,
    count_cookies_by_domain_in_firefox_db,
)


class TestFullCleanWorkflow:
    """Test complete scan -> review -> clean workflow."""

    def test_scan_review_clean_cycle(
        self,
        multi_profile_setup: dict,
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """
        Test complete workflow: scan -> select domains -> clean.

        PRD 12.1: Full scan -> review -> clean acceptance criteria.
        """
        stores = multi_profile_setup["stores"]
        paths = multi_profile_setup["paths"]

        # Step 1: Scan all profiles
        all_cookies: list[CookieRecord] = []
        for store in stores:
            reader = create_cookie_reader(store)
            all_cookies.extend(reader.read_cookies())

        initial_total = len(all_cookies)
        assert initial_total > 0

        # Step 2: Select domains to delete (tracker.com)
        target_domain = "tracker.com"
        cookies_to_delete = [c for c in all_cookies if c.domain == target_domain]
        assert len(cookies_to_delete) > 0

        # Step 3: Create delete plan
        plan = DeletePlan.create(dry_run=False)

        # Group cookies by store (using db_path as key since BrowserStore isn't hashable)
        store_map: dict[str, BrowserStore] = {}
        store_cookies: dict[str, list[CookieRecord]] = {}
        for cookie in cookies_to_delete:
            key = str(cookie.store.db_path)
            if key not in store_cookies:
                store_cookies[key] = []
                store_map[key] = cookie.store
            store_cookies[key].append(cookie)

        # Create operation for each store
        for key, cookies in store_cookies.items():
            store = store_map[key]
            raw_keys = {c.raw_host_key for c in cookies}
            targets = []
            for raw_key in raw_keys:
                count = len([c for c in cookies if c.raw_host_key == raw_key])
                targets.append(DeleteTarget(
                    normalized_domain=target_domain,
                    match_pattern=raw_key if not raw_key.startswith(".") else raw_key,
                    count=count,
                ))

            plan.add_operation(DeleteOperation(
                browser=store.browser_name,
                profile=store.profile_id,
                db_path=store.db_path,
                backup_path=temp_backup_dir / f"{store.browser_name}_{store.profile_id}.bak",
                targets=targets,
            ))

        # Step 4: Execute clean
        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan)

        # Step 5: Verify results
        assert report.success
        assert report.total_deleted > 0

        # PRD 12.1: Post-clean shows exact count
        assert report.total_deleted == len(cookies_to_delete)

        # Verify tracker.com cookies are gone
        for store in stores:
            reader = create_cookie_reader(store)
            remaining = reader.read_cookies()
            tracker_cookies = [c for c in remaining if c.domain == target_domain]
            assert len(tracker_cookies) == 0

    def test_backup_created_before_deletion(
        self,
        multi_profile_setup: dict,
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """
        Verify backup is created before any deletion.

        PRD 12.1: .bak file created before deletion.
        """
        stores = multi_profile_setup["stores"]
        chrome_store = next(s for s in stores if s.browser_name == "Chrome")

        initial_count = count_cookies_in_chromium_db(chrome_store.db_path)

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile=chrome_store.profile_id,
            db_path=chrome_store.db_path,
            backup_path=temp_backup_dir / "chrome.bak",
            targets=[
                DeleteTarget("google.com", "%.google.com", 2),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan)

        assert report.success

        # Verify backup exists
        backups = list(temp_backup_dir.rglob("*.bak"))
        assert len(backups) >= 1

        # Verify backup contains original data
        backup_path = backups[0]
        backup_count = count_cookies_in_chromium_db(backup_path)
        assert backup_count == initial_count  # Backup has original count


class TestDryRunWorkflow:
    """Test dry run functionality."""

    def test_dry_run_no_changes(
        self,
        multi_profile_setup: dict,
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """
        Verify dry run makes no changes.

        PRD 12.1: Dry run creates no backups, count = 0 actual deletes.
        """
        stores = multi_profile_setup["stores"]
        chrome_store = next(s for s in stores if s.browser_name == "Chrome")

        initial_count = count_cookies_in_chromium_db(chrome_store.db_path)

        plan = DeletePlan.create(dry_run=True)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile=chrome_store.profile_id,
            db_path=chrome_store.db_path,
            backup_path=temp_backup_dir / "chrome.bak",
            targets=[
                DeleteTarget("google.com", "%.google.com", 2),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan, dry_run=True)

        # Verify report
        assert report.success
        assert report.dry_run
        assert report.total_would_delete > 0  # Reports what WOULD be deleted
        assert report.total_deleted == 0  # No actual deletion in dry run

        # Verify no actual changes
        final_count = count_cookies_in_chromium_db(chrome_store.db_path)
        assert final_count == initial_count

        # Verify no backup created
        backups = list(temp_backup_dir.rglob("*.bak"))
        assert len(backups) == 0


class TestRestoreWorkflow:
    """Test backup restoration workflow."""

    def test_restore_from_backup(
        self,
        multi_profile_setup: dict,
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """
        Test full restore workflow: clean -> restore -> verify.

        PRD 12.1: Restore replaces DB, returns to Idle.
        """
        stores = multi_profile_setup["stores"]
        chrome_store = next(s for s in stores if s.browser_name == "Chrome")

        initial_count = count_cookies_in_chromium_db(chrome_store.db_path)

        # Step 1: Delete some cookies
        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile=chrome_store.profile_id,
            db_path=chrome_store.db_path,
            backup_path=temp_backup_dir / "chrome.bak",
            targets=[
                DeleteTarget("google.com", "%.google.com", 2),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan)

        assert report.success

        # Verify deletion occurred
        post_delete_count = count_cookies_in_chromium_db(chrome_store.db_path)
        assert post_delete_count < initial_count

        # Step 2: Get backup path
        backup_path = report.results[0].backup_path
        assert backup_path.exists()

        # Step 3: Restore from backup
        restore_success = backup_manager.restore_backup(
            backup_path, chrome_store.db_path
        )
        assert restore_success

        # Step 4: Verify restoration
        restored_count = count_cookies_in_chromium_db(chrome_store.db_path)
        assert restored_count == initial_count

    def test_get_latest_backup(
        self,
        multi_profile_setup: dict,
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Test getting the most recent backup."""
        stores = multi_profile_setup["stores"]
        chrome_store = next(s for s in stores if s.browser_name == "Chrome")

        backup_manager = BackupManager(temp_backup_dir)

        # Create first backup (via delete)
        # backup_path must be in backup_root/browser/profile/ for get_latest_backup to find it
        plan1 = DeletePlan.create(dry_run=False)
        plan1.add_operation(DeleteOperation(
            browser="Chrome",
            profile=chrome_store.profile_id,
            db_path=chrome_store.db_path,
            backup_path=temp_backup_dir / "Chrome" / chrome_store.profile_id / "first.bak",
            targets=[
                DeleteTarget("tracker.com", "%.tracker.com", 1),
            ],
        ))

        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )
        executor.execute(plan1)

        # Get latest backup
        latest = backup_manager.get_latest_backup("Chrome", chrome_store.profile_id)
        assert latest is not None
        assert latest.exists()


class TestAtomicDelete:
    """Test atomic delete behavior."""

    def test_atomic_delete_on_success(
        self,
        multi_profile_setup: dict,
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """
        Verify successful delete is atomic (all or nothing).

        PRD 12.1: Atomic delete - backup remains intact on crash.
        """
        stores = multi_profile_setup["stores"]
        chrome_store = next(s for s in stores if s.browser_name == "Chrome")

        # Get initial counts for multiple domains
        initial_google = count_cookies_by_domain_in_chromium_db(
            chrome_store.db_path, "%.google.com"
        )
        initial_facebook = count_cookies_by_domain_in_chromium_db(
            chrome_store.db_path, "%.facebook.com"
        )

        # Delete multiple domains in one plan
        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile=chrome_store.profile_id,
            db_path=chrome_store.db_path,
            backup_path=temp_backup_dir / "chrome.bak",
            targets=[
                DeleteTarget("google.com", "%.google.com", initial_google),
                DeleteTarget("facebook.com", "%.facebook.com", initial_facebook),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan)

        assert report.success

        # Verify both domains deleted
        final_google = count_cookies_by_domain_in_chromium_db(
            chrome_store.db_path, "%.google.com"
        )
        final_facebook = count_cookies_by_domain_in_chromium_db(
            chrome_store.db_path, "%.facebook.com"
        )

        assert final_google == 0
        assert final_facebook == 0

        # Verify backup has original data
        backup_path = report.results[0].backup_path
        backup_google = count_cookies_by_domain_in_chromium_db(
            backup_path, "%.google.com"
        )
        backup_facebook = count_cookies_by_domain_in_chromium_db(
            backup_path, "%.facebook.com"
        )

        assert backup_google == initial_google
        assert backup_facebook == initial_facebook


class TestDeletePlanSerialization:
    """Test DeletePlan JSON serialization for audit."""

    def test_delete_plan_to_json(
        self, multi_profile_setup: dict, temp_backup_dir: Path
    ):
        """Test DeletePlan serializes to valid JSON."""
        stores = multi_profile_setup["stores"]
        chrome_store = next(s for s in stores if s.browser_name == "Chrome")

        plan = DeletePlan.create(dry_run=False)
        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile=chrome_store.profile_id,
            db_path=chrome_store.db_path,
            backup_path=temp_backup_dir / "chrome.bak",
            targets=[
                DeleteTarget("google.com", "%.google.com", 2),
            ],
        ))

        # Serialize to JSON
        json_str = plan.to_json()
        assert json_str

        # Verify valid JSON
        parsed = json.loads(json_str)
        assert "plan_id" in parsed
        assert "timestamp" in parsed
        assert "dry_run" in parsed
        assert "operations" in parsed
        assert "summary" in parsed

        # Verify can reconstruct
        restored_plan = DeletePlan.from_json(json_str)
        assert restored_plan.plan_id == plan.plan_id
        assert restored_plan.dry_run == plan.dry_run
        assert len(restored_plan.operations) == len(plan.operations)


class TestMultiBrowserClean:
    """Test clean workflow across multiple browsers."""

    def test_clean_across_chrome_and_firefox(
        self,
        multi_profile_setup: dict,
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Test deleting same domain across Chrome and Firefox."""
        stores = multi_profile_setup["stores"]
        paths = multi_profile_setup["paths"]

        # Get a Chrome store and Firefox store
        chrome_store = next(s for s in stores if s.browser_name == "Chrome")
        firefox_store = next(s for s in stores if s.browser_name == "Firefox")

        # Domain present in both browsers: tracker.com
        target_domain = "tracker.com"

        # Initial counts
        chrome_initial = count_cookies_by_domain_in_chromium_db(
            chrome_store.db_path, "%tracker.com"
        )
        firefox_initial = count_cookies_by_domain_in_firefox_db(
            firefox_store.db_path, "%tracker.com"
        )

        assert chrome_initial > 0
        assert firefox_initial > 0

        # Create plan for both browsers
        plan = DeletePlan.create(dry_run=False)

        plan.add_operation(DeleteOperation(
            browser="Chrome",
            profile=chrome_store.profile_id,
            db_path=chrome_store.db_path,
            backup_path=temp_backup_dir / "chrome.bak",
            targets=[
                DeleteTarget(target_domain, "%.tracker.com", chrome_initial),
            ],
        ))

        plan.add_operation(DeleteOperation(
            browser="Firefox",
            profile=firefox_store.profile_id,
            db_path=firefox_store.db_path,
            backup_path=temp_backup_dir / "firefox.bak",
            targets=[
                DeleteTarget(target_domain, "%tracker.com", firefox_initial),
            ],
        ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan)

        assert report.success
        assert report.total_deleted == chrome_initial + firefox_initial

        # Verify deleted from both
        chrome_final = count_cookies_by_domain_in_chromium_db(
            chrome_store.db_path, "%tracker.com"
        )
        firefox_final = count_cookies_by_domain_in_firefox_db(
            firefox_store.db_path, "%tracker.com"
        )

        assert chrome_final == 0
        assert firefox_final == 0
