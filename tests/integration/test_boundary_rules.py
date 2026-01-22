"""Integration tests for domain boundary rules (Fixture A).

Verifies that deleting cookies for 'ample.com' does NOT affect:
- trample.com (contains 'ample.com' as substring)
- example.com (contains 'ample.com' as substring)

This is a critical safety test for the deletion engine.
"""

import sqlite3
from pathlib import Path

import pytest

from src.core.models import BrowserStore, DeleteOperation, DeletePlan, DeleteTarget
from src.execution.backup_manager import BackupManager
from src.execution.delete_executor import DeleteExecutor
from src.scanner.chromium_cookie_reader import ChromiumCookieReader
from src.scanner.firefox_cookie_reader import FirefoxCookieReader

from .conftest import (
    count_cookies_by_domain_in_chromium_db,
    count_cookies_by_domain_in_firefox_db,
    count_cookies_in_chromium_db,
    count_cookies_in_firefox_db,
)


class TestDomainBoundaryIsolation:
    """Test that domain deletion respects exact boundaries."""

    def test_ample_com_deletion_does_not_affect_trample_com_chromium(
        self,
        fixture_a_domain_boundary: dict[str, Path],
        fixture_a_stores: dict[str, BrowserStore],
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """
        Verify deleting ample.com cookies leaves trample.com untouched in Chromium.

        PRD 12.1 Acceptance Criteria: Domain boundary isolation.
        """
        chrome_path = fixture_a_domain_boundary["chrome"]
        chrome_store = fixture_a_stores["chrome"]

        # Count initial cookies using exact domain patterns
        # Note: %ample.com would also match trample.com, so we use specific patterns
        initial_dot_ample = count_cookies_by_domain_in_chromium_db(chrome_path, ".ample.com")
        initial_www_ample = count_cookies_by_domain_in_chromium_db(chrome_path, "www.ample.com")
        initial_trample = count_cookies_by_domain_in_chromium_db(chrome_path, "%.trample.com")
        # Note: %.example.com only matches .example.com, not example.com (no dot)
        initial_dot_example = count_cookies_by_domain_in_chromium_db(chrome_path, ".example.com")

        assert initial_dot_ample == 2  # .ample.com x2
        assert initial_www_ample == 1  # www.ample.com
        assert initial_trample == 3  # .trample.com x2 + sub.trample.com
        assert initial_dot_example == 1  # .example.com only

        # Create delete plan for ample.com ONLY
        # Use exact match patterns that won't catch trample.com or example.com
        plan = DeletePlan.create(dry_run=False)
        operation = DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                # Pattern must match .ample.com and ample.com but NOT trample.com
                DeleteTarget(
                    normalized_domain="ample.com",
                    match_pattern="%.ample.com",  # domain-wide cookies
                    count=2,
                ),
                DeleteTarget(
                    normalized_domain="ample.com",
                    match_pattern="www.ample.com",  # exact www
                    count=1,
                ),
            ],
        )
        plan.add_operation(operation)

        # Execute deletion
        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan)

        # Verify execution succeeded
        assert report.success
        assert report.total_deleted == 3

        # Verify ample.com cookies are gone
        final_ample = count_cookies_by_domain_in_chromium_db(chrome_path, "%ample.com")
        # Should still have trample.com (3) + example.com (2) = 5 remaining that contain "ample"
        # but our pattern was specific, so only exact ample.com matches are deleted

        # Re-query with more specific patterns
        remaining_dot_ample = count_cookies_by_domain_in_chromium_db(chrome_path, "%.ample.com")
        remaining_www_ample = count_cookies_by_domain_in_chromium_db(chrome_path, "www.ample.com")
        assert remaining_dot_ample == 0  # Deleted
        assert remaining_www_ample == 0  # Deleted

        # Verify trample.com is UNTOUCHED
        final_trample = count_cookies_by_domain_in_chromium_db(chrome_path, "%trample.com")
        assert final_trample == initial_trample  # Still 3

        # Verify example.com is UNTOUCHED
        final_dot_example = count_cookies_by_domain_in_chromium_db(chrome_path, ".example.com")
        assert final_dot_example == initial_dot_example  # Still 1

    def test_ample_com_deletion_does_not_affect_trample_com_firefox(
        self,
        fixture_a_domain_boundary: dict[str, Path],
        fixture_a_stores: dict[str, BrowserStore],
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """
        Verify deleting ample.com cookies leaves trample.com untouched in Firefox.
        """
        firefox_path = fixture_a_domain_boundary["firefox"]
        firefox_store = fixture_a_stores["firefox"]

        # Count initial cookies using specific patterns
        # Note: %ample.com would also match trample.com, so we use specific patterns
        initial_dot_ample = count_cookies_by_domain_in_firefox_db(firefox_path, ".ample.com")
        initial_exact_ample = count_cookies_by_domain_in_firefox_db(firefox_path, "ample.com")
        initial_trample = count_cookies_by_domain_in_firefox_db(firefox_path, "%trample.com")

        assert initial_dot_ample == 1  # .ample.com
        assert initial_exact_ample == 1  # ample.com
        assert initial_trample == 2  # trample.com + .trample.com

        # Create delete plan for ample.com ONLY
        plan = DeletePlan.create(dry_run=False)
        operation = DeleteOperation(
            browser="Firefox",
            profile="profile",
            db_path=firefox_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="ample.com",
                    match_pattern="%.ample.com",
                    count=1,
                ),
                DeleteTarget(
                    normalized_domain="ample.com",
                    match_pattern="ample.com",
                    count=1,
                ),
            ],
        )
        plan.add_operation(operation)

        # Execute deletion
        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan)

        assert report.success
        assert report.total_deleted == 2

        # Verify trample.com is UNTOUCHED
        final_trample = count_cookies_by_domain_in_firefox_db(firefox_path, "%trample.com")
        assert final_trample == initial_trample  # Still 2

    def test_dry_run_preserves_all_cookies(
        self,
        fixture_a_domain_boundary: dict[str, Path],
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """
        Verify dry run mode doesn't delete any cookies.

        PRD 12.1 Acceptance Criteria: Dry run creates no backups, count = 0.
        """
        chrome_path = fixture_a_domain_boundary["chrome"]

        initial_total = count_cookies_in_chromium_db(chrome_path)

        # Create delete plan with dry_run=True
        # Use specific pattern that only matches .ample.com cookies
        plan = DeletePlan.create(dry_run=True)
        operation = DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="ample.com",
                    match_pattern=".ample.com",  # Exact match for .ample.com
                    count=2,
                ),
            ],
        )
        plan.add_operation(operation)

        # Execute in dry run mode
        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan, dry_run=True)

        # Verify dry run reports what would be deleted
        assert report.success
        assert report.dry_run
        # The dry run counts actual matches in the DB
        assert report.total_deleted >= 1  # Reports count, doesn't actually delete

        # Verify no actual deletion occurred
        final_total = count_cookies_in_chromium_db(chrome_path)
        assert final_total == initial_total

        # Verify no backup was created
        backups = list(temp_backup_dir.rglob("*.bak"))
        assert len(backups) == 0


class TestSubstringDomainSafety:
    """Test protection against substring-based false matches."""

    def test_deleting_ads_com_does_not_affect_leads_com(
        self,
        integration_temp_dir: Path,
        golden_factory,
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Verify 'ads.com' deletion doesn't affect 'leads.com'."""
        # Create test database
        db_path = integration_temp_dir / "substring_test" / "Cookies"
        db_path.parent.mkdir(parents=True)
        golden_factory.create_chromium_db(db_path, [
            (".ads.com", "tracking", None, 0),
            ("ads.com", "session", None, 1),
            (".leads.com", "crm", None, 1),
            ("leads.com", "user", None, 1),
            (".beads.com", "prefs", None, 0),
        ])

        initial_ads = count_cookies_by_domain_in_chromium_db(db_path, "%ads.com")
        initial_leads = count_cookies_by_domain_in_chromium_db(db_path, "%leads.com")
        initial_beads = count_cookies_by_domain_in_chromium_db(db_path, "%beads.com")

        # Pattern for ads.com must be exact
        plan = DeletePlan.create(dry_run=False)
        operation = DeleteOperation(
            browser="Chrome",
            profile="Test",
            db_path=db_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="ads.com",
                    match_pattern="%.ads.com",
                    count=1,
                ),
                DeleteTarget(
                    normalized_domain="ads.com",
                    match_pattern="ads.com",
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

        # Verify leads.com and beads.com are untouched
        final_leads = count_cookies_by_domain_in_chromium_db(db_path, "%leads.com")
        final_beads = count_cookies_by_domain_in_chromium_db(db_path, "%beads.com")

        assert final_leads == initial_leads
        assert final_beads == initial_beads

    def test_facebook_deletion_isolated_from_fakebook(
        self,
        integration_temp_dir: Path,
        golden_factory,
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Verify 'facebook.com' deletion doesn't affect 'fakebook.com'."""
        db_path = integration_temp_dir / "fb_test" / "Cookies"
        db_path.parent.mkdir(parents=True)
        golden_factory.create_chromium_db(db_path, [
            (".facebook.com", "c_user", None, 1),
            (".facebook.com", "xs", None, 1),
            (".fakebook.com", "session", None, 1),
            (".myfacebook.com", "data", None, 0),
        ])

        initial_facebook = count_cookies_by_domain_in_chromium_db(db_path, "%.facebook.com")
        initial_fakebook = count_cookies_by_domain_in_chromium_db(db_path, "%.fakebook.com")
        initial_myfacebook = count_cookies_by_domain_in_chromium_db(db_path, "%.myfacebook.com")

        assert initial_facebook == 2
        assert initial_fakebook == 1
        assert initial_myfacebook == 1

        plan = DeletePlan.create(dry_run=False)
        operation = DeleteOperation(
            browser="Chrome",
            profile="Test",
            db_path=db_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="facebook.com",
                    match_pattern="%.facebook.com",
                    count=2,
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
        assert report.total_deleted == 2

        # Verify facebook.com deleted
        final_facebook = count_cookies_by_domain_in_chromium_db(db_path, "%.facebook.com")
        assert final_facebook == 0

        # Verify similar domains untouched
        final_fakebook = count_cookies_by_domain_in_chromium_db(db_path, "%.fakebook.com")
        final_myfacebook = count_cookies_by_domain_in_chromium_db(db_path, "%.myfacebook.com")
        assert final_fakebook == initial_fakebook
        assert final_myfacebook == initial_myfacebook


class TestSQLPatternMatching:
    """Test SQL LIKE pattern matching edge cases."""

    def test_pattern_with_underscore_domain(
        self,
        integration_temp_dir: Path,
        golden_factory,
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Test domains containing underscores (rare but valid).

        Note: SQL LIKE treats '_' as a wildcard matching any single character.
        To exactly match a domain with underscores, use exact host_key match.
        """
        db_path = integration_temp_dir / "underscore_test" / "Cookies"
        db_path.parent.mkdir(parents=True)
        golden_factory.create_chromium_db(db_path, [
            (".test_site.com", "cookie1", None, 1),
            (".other_domain.com", "cookie2", None, 1),  # Different underscore domain
        ])

        # Delete only test_site.com using exact match
        plan = DeletePlan.create(dry_run=False)
        operation = DeleteOperation(
            browser="Chrome",
            profile="Test",
            db_path=db_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="test_site.com",
                    match_pattern=".test_site.com",  # Exact match
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

        # Verify only test_site.com was deleted
        remaining_test_site = count_cookies_by_domain_in_chromium_db(db_path, ".test_site.com")
        remaining_other = count_cookies_by_domain_in_chromium_db(db_path, ".other_domain.com")

        assert remaining_test_site == 0  # Deleted
        assert remaining_other == 1  # Preserved

    def test_pattern_with_special_tld(
        self,
        integration_temp_dir: Path,
        golden_factory,
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Test domains with multi-part TLDs like .co.uk."""
        db_path = integration_temp_dir / "tld_test" / "Cookies"
        db_path.parent.mkdir(parents=True)
        golden_factory.create_chromium_db(db_path, [
            (".example.co.uk", "uk_cookie", None, 1),
            (".example.com", "com_cookie", None, 1),
            (".example.co", "co_cookie", None, 1),
        ])

        # Delete only example.co.uk
        plan = DeletePlan.create(dry_run=False)
        operation = DeleteOperation(
            browser="Chrome",
            profile="Test",
            db_path=db_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="example.co.uk",
                    match_pattern="%.example.co.uk",
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

        # Verify isolation
        remaining_uk = count_cookies_by_domain_in_chromium_db(db_path, "%.example.co.uk")
        remaining_com = count_cookies_by_domain_in_chromium_db(db_path, "%.example.com")
        remaining_co = count_cookies_by_domain_in_chromium_db(db_path, "%.example.co")

        assert remaining_uk == 0  # Deleted
        assert remaining_com == 1  # Preserved
        assert remaining_co == 1  # Preserved (example.co is different from example.co.uk)
