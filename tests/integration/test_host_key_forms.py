"""Integration tests for host key form variations (Fixture B).

Tests different cookie host_key formats:
- .example.com (domain-wide cookies)
- example.com (exact host cookies)
- www.example.com (subdomain cookies)
- api.example.com (subdomain cookies)

Verifies the deletion engine handles all forms correctly.
"""

import sqlite3
from pathlib import Path

import pytest

from src.core.models import BrowserStore, DeleteOperation, DeletePlan, DeleteTarget
from src.execution.backup_manager import BackupManager
from src.execution.delete_executor import DeleteExecutor
from src.scanner.chromium_cookie_reader import ChromiumCookieReader

from .conftest import (
    count_cookies_by_domain_in_chromium_db,
    count_cookies_in_chromium_db,
)


class TestHostKeyFormats:
    """Test deletion with various host_key formats."""

    def test_dot_prefix_domain_cookies_deleted(
        self,
        fixture_b_host_key_forms: dict[str, Path],
        fixture_b_store: BrowserStore,
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Verify .example.com pattern deletes domain-wide cookies."""
        chrome_path = fixture_b_host_key_forms["chrome"]

        # Initial count
        initial_dot_example = count_cookies_by_domain_in_chromium_db(
            chrome_path, ".example.com"
        )
        assert initial_dot_example == 1

        plan = DeletePlan.create(dry_run=False)
        operation = DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="example.com",
                    match_pattern=".example.com",  # Exact match for domain cookie
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

        # Verify .example.com deleted
        final_dot_example = count_cookies_by_domain_in_chromium_db(
            chrome_path, ".example.com"
        )
        assert final_dot_example == 0

        # Verify other example.com subdomains still exist
        remaining_www = count_cookies_by_domain_in_chromium_db(
            chrome_path, "www.example.com"
        )
        remaining_api = count_cookies_by_domain_in_chromium_db(
            chrome_path, "api.example.com"
        )
        assert remaining_www == 1
        assert remaining_api == 1

    def test_exact_host_cookie_deleted(
        self,
        fixture_b_host_key_forms: dict[str, Path],
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Verify example.com (no dot) exact match works."""
        chrome_path = fixture_b_host_key_forms["chrome"]

        initial_exact = count_cookies_by_domain_in_chromium_db(
            chrome_path, "example.com"
        )
        # Note: example.com without leading dot (exact host)
        assert initial_exact == 1

        plan = DeletePlan.create(dry_run=False)
        operation = DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="example.com",
                    match_pattern="example.com",  # Exact match (no dot)
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

    def test_delete_all_example_com_variations(
        self,
        fixture_b_host_key_forms: dict[str, Path],
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Delete all example.com cookies using wildcard pattern."""
        chrome_path = fixture_b_host_key_forms["chrome"]

        # Count all example.com variations
        conn = sqlite3.connect(chrome_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM cookies WHERE host_key LIKE ?",
            ("%example.com",),
        )
        initial_all_example = cursor.fetchone()[0]
        conn.close()

        assert initial_all_example == 5  # .example.com, example.com, www, api, sub.api

        # Delete using wildcard that catches all
        plan = DeletePlan.create(dry_run=False)
        operation = DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="example.com",
                    match_pattern="%example.com",  # Catches all variations
                    count=5,
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
        assert report.total_deleted == 5

        # Verify all deleted
        conn = sqlite3.connect(chrome_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM cookies WHERE host_key LIKE ?",
            ("%example.com",),
        )
        final_count = cursor.fetchone()[0]
        conn.close()

        assert final_count == 0

        # Verify other.com untouched
        remaining_other = count_cookies_by_domain_in_chromium_db(
            chrome_path, "%.other.com"
        )
        assert remaining_other == 1

    def test_subdomain_isolation(
        self,
        fixture_b_host_key_forms: dict[str, Path],
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Verify deleting www.example.com doesn't affect api.example.com."""
        chrome_path = fixture_b_host_key_forms["chrome"]

        initial_www = count_cookies_by_domain_in_chromium_db(
            chrome_path, "www.example.com"
        )
        initial_api = count_cookies_by_domain_in_chromium_db(
            chrome_path, "api.example.com"
        )
        assert initial_www == 1
        assert initial_api == 1

        plan = DeletePlan.create(dry_run=False)
        operation = DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="www.example.com",
                    match_pattern="www.example.com",
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

        # www deleted, api preserved
        final_www = count_cookies_by_domain_in_chromium_db(
            chrome_path, "www.example.com"
        )
        final_api = count_cookies_by_domain_in_chromium_db(
            chrome_path, "api.example.com"
        )

        assert final_www == 0
        assert final_api == 1

    def test_deep_subdomain_deletion(
        self,
        fixture_b_host_key_forms: dict[str, Path],
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """Test deletion of deeply nested subdomains like sub.api.example.com."""
        chrome_path = fixture_b_host_key_forms["chrome"]

        initial_deep = count_cookies_by_domain_in_chromium_db(
            chrome_path, "sub.api.example.com"
        )
        assert initial_deep == 1

        plan = DeletePlan.create(dry_run=False)
        operation = DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=chrome_path,
            backup_path=temp_backup_dir / "backup.bak",
            targets=[
                DeleteTarget(
                    normalized_domain="sub.api.example.com",
                    match_pattern="sub.api.example.com",
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

        # Verify api.example.com still exists
        remaining_api = count_cookies_by_domain_in_chromium_db(
            chrome_path, "api.example.com"
        )
        assert remaining_api == 1


class TestHostKeyReading:
    """Test that cookie readers correctly parse host_key formats."""

    def test_reader_normalizes_dot_prefix(
        self, fixture_b_host_key_forms: dict[str, Path], fixture_b_store: BrowserStore
    ):
        """Verify reader normalizes .example.com to example.com for display."""
        reader = ChromiumCookieReader(fixture_b_store)
        cookies = reader.read_cookies()

        # Find cookies with .example.com raw_host_key
        domain_cookies = [c for c in cookies if c.raw_host_key == ".example.com"]
        assert len(domain_cookies) == 1

        # Normalized domain should not have dot
        assert domain_cookies[0].domain == "example.com"

        # Raw host_key should preserve the dot
        assert domain_cookies[0].raw_host_key == ".example.com"

    def test_reader_preserves_exact_host(
        self, fixture_b_host_key_forms: dict[str, Path], fixture_b_store: BrowserStore
    ):
        """Verify reader preserves example.com (no dot) correctly."""
        reader = ChromiumCookieReader(fixture_b_store)
        cookies = reader.read_cookies()

        # Find cookie with exact host (no dot)
        exact_cookies = [c for c in cookies if c.raw_host_key == "example.com"]
        assert len(exact_cookies) == 1

        # Both should be "example.com" (no normalization needed)
        assert exact_cookies[0].domain == "example.com"
        assert exact_cookies[0].raw_host_key == "example.com"

    def test_reader_handles_subdomain_host_keys(
        self, fixture_b_host_key_forms: dict[str, Path], fixture_b_store: BrowserStore
    ):
        """Verify reader correctly handles subdomain host_keys."""
        reader = ChromiumCookieReader(fixture_b_store)
        cookies = reader.read_cookies()

        # Check www subdomain
        www_cookies = [c for c in cookies if c.raw_host_key == "www.example.com"]
        assert len(www_cookies) == 1
        assert www_cookies[0].domain == "www.example.com"

        # Check api subdomain
        api_cookies = [c for c in cookies if c.raw_host_key == "api.example.com"]
        assert len(api_cookies) == 1
        assert api_cookies[0].domain == "api.example.com"

        # Check deep subdomain
        deep_cookies = [c for c in cookies if c.raw_host_key == "sub.api.example.com"]
        assert len(deep_cookies) == 1
        assert deep_cookies[0].domain == "sub.api.example.com"
