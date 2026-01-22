"""Integration tests for full scan workflow.

Tests end-to-end scanning across multiple browsers and profiles:
- Multi-browser scanning (Chrome, Firefox)
- Multi-profile scanning (Chrome Default + Profile 1)
- Cookie aggregation by domain
- BrowserStore detection
"""

from pathlib import Path
from collections import defaultdict

import pytest

from src.core.models import BrowserStore, CookieRecord, DomainAggregate
from src.scanner.chromium_cookie_reader import ChromiumCookieReader
from src.scanner.firefox_cookie_reader import FirefoxCookieReader
from src.scanner.cookie_reader import create_reader as create_cookie_reader


class TestMultiProfileScanning:
    """Test scanning across multiple profiles."""

    def test_scan_multiple_chrome_profiles(
        self, multi_profile_setup: dict
    ):
        """
        Verify scanning detects 2+ Chrome profiles.

        PRD 12.1: Multi-Profile detection.
        """
        stores = multi_profile_setup["stores"]

        # Filter Chrome stores
        chrome_stores = [s for s in stores if s.browser_name == "Chrome"]
        assert len(chrome_stores) >= 2  # Default + Profile 1

        # Verify profiles are distinct
        profile_ids = [s.profile_id for s in chrome_stores]
        assert len(set(profile_ids)) == len(profile_ids)  # No duplicates

        # Verify each can be scanned
        for store in chrome_stores:
            reader = create_cookie_reader(store)
            cookies = reader.read_cookies()
            assert len(cookies) > 0, f"No cookies found in {store.profile_id}"

    def test_scan_firefox_profile(
        self, multi_profile_setup: dict
    ):
        """
        Verify scanning detects 1+ Firefox profile.

        PRD 12.1: Multi-Profile detection.
        """
        stores = multi_profile_setup["stores"]

        # Filter Firefox stores
        firefox_stores = [s for s in stores if s.browser_name == "Firefox"]
        assert len(firefox_stores) >= 1

        # Verify can be scanned
        for store in firefox_stores:
            reader = create_cookie_reader(store)
            cookies = reader.read_cookies()
            assert len(cookies) > 0


class TestCookieAggregation:
    """Test cookie aggregation by domain."""

    def test_aggregate_cookies_by_domain(
        self, multi_profile_setup: dict
    ):
        """Test aggregating cookies from all sources by domain."""
        stores = multi_profile_setup["stores"]

        # Collect all cookies
        all_cookies: list[CookieRecord] = []
        for store in stores:
            reader = create_cookie_reader(store)
            all_cookies.extend(reader.read_cookies())

        # Aggregate by normalized domain
        domain_map: dict[str, list[CookieRecord]] = defaultdict(list)
        for cookie in all_cookies:
            domain_map[cookie.domain].append(cookie)

        # Create DomainAggregate objects
        aggregates: list[DomainAggregate] = []
        for domain, cookies in domain_map.items():
            browsers = {c.store.browser_name for c in cookies}
            raw_host_keys = {c.raw_host_key for c in cookies}
            aggregate = DomainAggregate(
                normalized_domain=domain,
                cookie_count=len(cookies),
                browsers=browsers,
                records=cookies,
                raw_host_keys=raw_host_keys,
            )
            aggregates.append(aggregate)

        # Verify aggregation works
        assert len(aggregates) > 0

        # Find google.com aggregate (should have cookies from both Chrome and Firefox)
        google_agg = next(
            (a for a in aggregates if a.normalized_domain == "google.com"), None
        )
        assert google_agg is not None
        assert google_agg.cookie_count >= 3  # Multiple cookies across profiles
        assert len(google_agg.browsers) >= 1  # At least Chrome

        # Find tracker.com aggregate
        tracker_agg = next(
            (a for a in aggregates if a.normalized_domain == "tracker.com"), None
        )
        assert tracker_agg is not None
        assert tracker_agg.cookie_count >= 2

    def test_domain_normalization_consistency(
        self, multi_profile_setup: dict
    ):
        """Verify domain normalization is consistent across browsers."""
        stores = multi_profile_setup["stores"]

        all_cookies: list[CookieRecord] = []
        for store in stores:
            reader = create_cookie_reader(store)
            all_cookies.extend(reader.read_cookies())

        # Check that normalized domains don't have leading dots
        for cookie in all_cookies:
            assert not cookie.domain.startswith("."), \
                f"Normalized domain should not have leading dot: {cookie.domain}"

            # raw_host_key may have dots
            assert cookie.raw_host_key  # Should not be empty


class TestBrowserStoreDetection:
    """Test BrowserStore properties and detection."""

    def test_chromium_store_is_chromium_true(
        self, multi_profile_setup: dict
    ):
        """Verify Chrome/Edge stores have is_chromium=True."""
        stores = multi_profile_setup["stores"]

        chrome_stores = [s for s in stores if s.browser_name == "Chrome"]
        for store in chrome_stores:
            assert store.is_chromium

    def test_firefox_store_is_chromium_false(
        self, multi_profile_setup: dict
    ):
        """Verify Firefox stores have is_chromium=False."""
        stores = multi_profile_setup["stores"]

        firefox_stores = [s for s in stores if s.browser_name == "Firefox"]
        for store in firefox_stores:
            assert not store.is_chromium

    def test_create_reader_returns_correct_type(
        self, multi_profile_setup: dict
    ):
        """Verify create_cookie_reader returns correct reader type."""
        stores = multi_profile_setup["stores"]

        for store in stores:
            reader = create_cookie_reader(store)
            if store.is_chromium:
                assert isinstance(reader, ChromiumCookieReader)
            else:
                assert isinstance(reader, FirefoxCookieReader)


class TestScanResults:
    """Test scan result completeness."""

    def test_scan_returns_all_cookie_attributes(
        self, multi_profile_setup: dict
    ):
        """Verify scanned cookies have all required attributes."""
        stores = multi_profile_setup["stores"]

        for store in stores:
            reader = create_cookie_reader(store)
            cookies = reader.read_cookies()

            for cookie in cookies:
                # Required attributes
                assert cookie.domain
                assert cookie.raw_host_key
                assert cookie.name
                assert cookie.store is not None

                # Store reference is correct
                assert cookie.store == store
                assert cookie.store.browser_name == store.browser_name

    def test_scan_handles_session_cookies(
        self, multi_profile_setup: dict
    ):
        """Verify session cookies (no expiry) are handled."""
        stores = multi_profile_setup["stores"]

        # Collect all cookies
        all_cookies: list[CookieRecord] = []
        for store in stores:
            reader = create_cookie_reader(store)
            all_cookies.extend(reader.read_cookies())

        # Check for session cookies (expires is None or 0)
        session_cookies = [c for c in all_cookies if c.expires is None]

        # There should be at least some session cookies in test data
        # (Our fixtures include some)
        # This verifies session cookies don't cause errors
        for cookie in session_cookies:
            assert cookie.domain  # Still has domain
            assert cookie.name  # Still has name


class TestCrossProfileDomainPresence:
    """Test domain presence across profiles."""

    def test_same_domain_in_multiple_profiles(
        self, multi_profile_setup: dict
    ):
        """Verify the same domain can appear in multiple profiles."""
        stores = multi_profile_setup["stores"]

        # Aggregate by domain
        domain_to_stores: dict[str, set[str]] = defaultdict(set)

        for store in stores:
            reader = create_cookie_reader(store)
            cookies = reader.read_cookies()
            for cookie in cookies:
                store_key = f"{store.browser_name}:{store.profile_id}"
                domain_to_stores[cookie.domain].add(store_key)

        # google.com should appear in multiple profiles
        google_stores = domain_to_stores.get("google.com", set())
        assert len(google_stores) >= 2, \
            f"google.com should be in multiple profiles, found in: {google_stores}"

        # tracker.com should appear in multiple profiles
        tracker_stores = domain_to_stores.get("tracker.com", set())
        assert len(tracker_stores) >= 2

    def test_unique_domain_counts_per_profile(
        self, multi_profile_setup: dict
    ):
        """Get unique domain count per profile."""
        stores = multi_profile_setup["stores"]

        for store in stores:
            reader = create_cookie_reader(store)
            cookies = reader.read_cookies()
            unique_domains = {c.domain for c in cookies}

            assert len(unique_domains) > 0, \
                f"No unique domains in {store.browser_name}/{store.profile_id}"


class TestScanWorkflowIntegration:
    """Full scan workflow integration tests."""

    def test_complete_scan_workflow(
        self, multi_profile_setup: dict
    ):
        """
        Test complete scan workflow end-to-end.

        1. Discover profiles (simulated via fixture)
        2. Scan each profile
        3. Aggregate results
        4. Produce summary
        """
        stores = multi_profile_setup["stores"]

        # Step 1: Profiles discovered (via fixture)
        assert len(stores) >= 3  # 2 Chrome + 1 Firefox

        # Step 2: Scan each profile
        profile_results = []
        for store in stores:
            reader = create_cookie_reader(store)
            cookies = reader.read_cookies()
            profile_results.append({
                "store": store,
                "cookie_count": len(cookies),
                "cookies": cookies,
            })

        # Step 3: Aggregate results
        all_cookies = []
        for result in profile_results:
            all_cookies.extend(result["cookies"])

        domain_map: dict[str, DomainAggregate] = {}
        for cookie in all_cookies:
            if cookie.domain not in domain_map:
                domain_map[cookie.domain] = DomainAggregate(
                    normalized_domain=cookie.domain,
                    cookie_count=0,
                    browsers=set(),
                    records=[],
                    raw_host_keys=set(),
                )
            agg = domain_map[cookie.domain]
            agg.cookie_count += 1
            agg.browsers.add(cookie.store.browser_name)
            agg.records.append(cookie)
            agg.raw_host_keys.add(cookie.raw_host_key)

        # Step 4: Summary
        total_cookies = sum(r["cookie_count"] for r in profile_results)
        unique_domains = len(domain_map)
        browsers_found = {s.browser_name for s in stores}
        profiles_found = len(stores)

        # Verify summary
        assert total_cookies > 0
        assert unique_domains > 0
        assert profiles_found >= 3
        assert "Chrome" in browsers_found
        assert "Firefox" in browsers_found
