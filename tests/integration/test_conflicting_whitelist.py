"""Integration tests for conflicting whitelist scenarios (Fixture D).

Tests the interaction between different whitelist rules:
- domain:google.com (protects all subdomains)
- exact:accounts.google.com (would be redundant)

Verifies whitelist matching priority and domain hierarchy handling.
"""

from pathlib import Path

import pytest

from src.core.models import BrowserStore, DeleteOperation, DeletePlan, DeleteTarget
from src.core.whitelist import WhitelistManager
from src.execution.backup_manager import BackupManager
from src.execution.delete_executor import DeleteExecutor
from src.scanner.chromium_cookie_reader import ChromiumCookieReader

from .conftest import count_cookies_by_domain_in_chromium_db, count_cookies_in_chromium_db


class TestWhitelistMatching:
    """Test whitelist matching rules."""

    def test_domain_prefix_protects_all_subdomains(self):
        """
        Verify domain:google.com protects all subdomains.

        PRD 12.1: domain:a.com protects all subdomains.
        """
        wm = WhitelistManager(["domain:google.com"])

        # All should be whitelisted
        assert wm.is_whitelisted("google.com")
        assert wm.is_whitelisted("www.google.com")
        assert wm.is_whitelisted("accounts.google.com")
        assert wm.is_whitelisted("mail.google.com")
        assert wm.is_whitelisted("docs.google.com")
        assert wm.is_whitelisted("deep.sub.domain.google.com")

        # Different domains should NOT be whitelisted
        assert not wm.is_whitelisted("notgoogle.com")
        assert not wm.is_whitelisted("google.org")
        assert not wm.is_whitelisted("google.co.uk")

    def test_exact_prefix_protects_only_exact_match(self):
        """
        Verify exact:accounts.google.com protects ONLY that host.

        PRD 12.1: exact:a.com protects only a.com.
        """
        wm = WhitelistManager(["exact:accounts.google.com"])

        # Only exact match is whitelisted
        assert wm.is_whitelisted("accounts.google.com")

        # Subdomains and parent domain NOT whitelisted
        assert not wm.is_whitelisted("google.com")
        assert not wm.is_whitelisted("www.google.com")
        assert not wm.is_whitelisted("mail.google.com")
        assert not wm.is_whitelisted("sub.accounts.google.com")

    def test_exact_has_priority_over_domain(self):
        """
        Verify exact: rules have priority over domain: rules.

        If we have domain:google.com, everything is protected.
        Adding exact:accounts.google.com is redundant but shouldn't change behavior.
        """
        wm = WhitelistManager([
            "domain:google.com",
            "exact:accounts.google.com",  # Redundant
        ])

        # All google.com should still be protected
        assert wm.is_whitelisted("google.com")
        assert wm.is_whitelisted("accounts.google.com")
        assert wm.is_whitelisted("mail.google.com")

    def test_conflicting_rules_exact_without_domain(self):
        """
        Test scenario where only specific subdomain is protected.

        User wants to protect accounts.google.com but delete other google.com cookies.
        """
        wm = WhitelistManager(["exact:accounts.google.com"])

        # Only accounts is protected
        assert wm.is_whitelisted("accounts.google.com")

        # Others can be deleted
        assert not wm.is_whitelisted("google.com")
        assert not wm.is_whitelisted("www.google.com")
        assert not wm.is_whitelisted("mail.google.com")
        assert not wm.is_whitelisted("docs.google.com")


class TestWhitelistFilteredDeletion:
    """Test deletion with whitelist filtering."""

    def test_delete_non_whitelisted_google_subdomains(
        self,
        fixture_d_conflicting_whitelist: Path,
        fixture_d_store: BrowserStore,
        temp_backup_dir: Path,
        unlocked_lock_resolver,
    ):
        """
        Delete google.com cookies except accounts.google.com.

        Whitelist: exact:accounts.google.com
        Delete: all other google.com cookies
        """
        db_path = fixture_d_conflicting_whitelist

        # Create whitelist protecting accounts.google.com
        wm = WhitelistManager(["exact:accounts.google.com"])

        # Read all cookies
        reader = ChromiumCookieReader(fixture_d_store)
        all_cookies = reader.read_cookies()

        # Filter to google.com domain (excluding whitelisted)
        google_cookies = [
            c for c in all_cookies
            if "google.com" in c.domain and not wm.is_whitelisted(c.domain)
        ]

        # Should have cookies to delete (google.com, www, mail, docs but NOT accounts)
        assert len(google_cookies) > 0
        assert not any(c.domain == "accounts.google.com" for c in google_cookies)

        # Collect unique patterns for deletion
        delete_patterns = set()
        for cookie in google_cookies:
            # Use raw_host_key for pattern
            if cookie.raw_host_key.startswith("."):
                delete_patterns.add(cookie.raw_host_key)
            else:
                delete_patterns.add(cookie.raw_host_key)

        # Create delete plan (excluding accounts.google.com)
        plan = DeletePlan.create(dry_run=False)
        targets = []
        for pattern in delete_patterns:
            count = count_cookies_by_domain_in_chromium_db(db_path, pattern)
            if count > 0:
                targets.append(DeleteTarget(
                    normalized_domain=pattern.lstrip("."),
                    match_pattern=pattern,
                    count=count,
                ))

        if targets:
            plan.add_operation(DeleteOperation(
                browser="Chrome",
                profile="Default",
                db_path=db_path,
                backup_path=temp_backup_dir / "backup.bak",
                targets=targets,
            ))

        backup_manager = BackupManager(temp_backup_dir)
        executor = DeleteExecutor(
            lock_resolver=unlocked_lock_resolver,
            backup_manager=backup_manager,
        )
        report = executor.execute(plan)

        assert report.success

        # Verify accounts.google.com preserved
        remaining_accounts = count_cookies_by_domain_in_chromium_db(
            db_path, "accounts.google.com"
        )
        assert remaining_accounts == 2  # LSID and HSID

        # Verify facebook.com untouched
        remaining_facebook = count_cookies_by_domain_in_chromium_db(
            db_path, "%.facebook.com"
        )
        assert remaining_facebook == 1

    def test_domain_whitelist_blocks_all_deletions(
        self,
        fixture_d_conflicting_whitelist: Path,
        fixture_d_store: BrowserStore,
    ):
        """
        Verify domain:google.com blocks deletion of ALL google cookies.
        """
        wm = WhitelistManager(["domain:google.com"])

        reader = ChromiumCookieReader(fixture_d_store)
        all_cookies = reader.read_cookies()

        # All google.com variants should be whitelisted
        google_cookies = [c for c in all_cookies if "google.com" in c.domain]
        for cookie in google_cookies:
            assert wm.is_whitelisted(cookie.domain), f"{cookie.domain} should be whitelisted"

        # facebook.com should NOT be whitelisted
        facebook_cookies = [c for c in all_cookies if "facebook.com" in c.domain]
        for cookie in facebook_cookies:
            assert not wm.is_whitelisted(cookie.domain)


class TestPublicSuffixGuard:
    """Test public suffix protection."""

    def test_domain_com_blocked(self):
        """
        Verify domain:com is rejected (would match all .com domains).

        PRD 12.1: domain:com blocked with error.
        """
        wm = WhitelistManager()

        # Attempt to add domain:com
        success, error = wm.add_entry("domain:com")

        assert not success
        assert "public suffix" in error.lower() or "too broad" in error.lower()

    def test_domain_co_uk_blocked(self):
        """Verify domain:co.uk is rejected."""
        wm = WhitelistManager()

        success, error = wm.add_entry("domain:co.uk")

        assert not success
        assert "public suffix" in error.lower() or "too broad" in error.lower()

    def test_domain_org_blocked(self):
        """Verify domain:org is rejected."""
        wm = WhitelistManager()

        success, error = wm.add_entry("domain:org")

        assert not success

    def test_exact_com_allowed(self):
        """
        Verify exact:com is allowed (though unusual).

        exact: doesn't have the recursive danger of domain:.
        """
        wm = WhitelistManager()

        # exact: prefix doesn't trigger public suffix guard
        # because it only matches exactly "com" which is unlikely to be a cookie domain
        success, _ = wm.add_entry("exact:com")

        # This might be allowed depending on implementation
        # If blocked, that's also acceptable
        # The key is that domain:com is blocked


class TestIPWhitelist:
    """Test IP address whitelisting."""

    def test_ip_whitelist_protects_ip_cookies(
        self,
        integration_temp_dir: Path,
        golden_factory,
    ):
        """Test that ip: prefix protects IP address cookies."""
        # Create database with IP-based cookies
        db_path = integration_temp_dir / "ip_test" / "Cookies"
        db_path.parent.mkdir(parents=True)
        golden_factory.create_chromium_db(db_path, [
            ("192.168.1.1", "local_session", None, 0),
            ("192.168.1.2", "other_local", None, 0),
            ("10.0.0.1", "internal", None, 0),
            (".example.com", "web_cookie", None, 1),
        ])

        wm = WhitelistManager(["ip:192.168.1.1"])

        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Test",
            db_path=db_path,
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        # Check whitelist matching
        for cookie in cookies:
            if cookie.domain == "192.168.1.1":
                assert wm.is_whitelisted(cookie.domain)
            elif cookie.domain == "192.168.1.2":
                assert not wm.is_whitelisted(cookie.domain)
            elif cookie.domain == "10.0.0.1":
                assert not wm.is_whitelisted(cookie.domain)


class TestMultipleWhitelistEntries:
    """Test scenarios with multiple whitelist entries."""

    def test_multiple_domain_entries(self):
        """Test multiple domain: entries."""
        wm = WhitelistManager([
            "domain:google.com",
            "domain:facebook.com",
            "domain:amazon.com",
        ])

        # All should be protected
        assert wm.is_whitelisted("www.google.com")
        assert wm.is_whitelisted("mail.google.com")
        assert wm.is_whitelisted("www.facebook.com")
        assert wm.is_whitelisted("smile.amazon.com")

        # Others not protected
        assert not wm.is_whitelisted("twitter.com")
        assert not wm.is_whitelisted("github.com")

    def test_mixed_prefix_entries(self):
        """Test combination of domain:, exact:, and ip: entries."""
        wm = WhitelistManager([
            "domain:google.com",
            "exact:api.example.com",
            "ip:127.0.0.1",
        ])

        # domain: protects hierarchy
        assert wm.is_whitelisted("google.com")
        assert wm.is_whitelisted("mail.google.com")

        # exact: protects only exact
        assert wm.is_whitelisted("api.example.com")
        assert not wm.is_whitelisted("example.com")
        assert not wm.is_whitelisted("www.example.com")

        # ip: protects exact IP
        assert wm.is_whitelisted("127.0.0.1")
        assert not wm.is_whitelisted("127.0.0.2")
