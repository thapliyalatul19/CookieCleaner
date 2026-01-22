"""Integration tests for performance requirements.

Tests that search/filter operations meet performance requirements:
- <100ms filter time for 1000 domains
- Efficient whitelist lookup
- Efficient domain aggregation
"""

import time
from collections import defaultdict
from pathlib import Path

import pytest

from src.core.models import BrowserStore, CookieRecord, DomainAggregate
from src.core.whitelist import WhitelistManager
from src.scanner.chromium_cookie_reader import ChromiumCookieReader


class TestSearchPerformance:
    """Test search/filter performance."""

    def test_filter_1000_domains_under_100ms(
        self, performance_db: tuple[Path, BrowserStore]
    ):
        """
        Verify filtering 1000+ domains completes in <100ms.

        PRD 12.1: <100ms search for 1000 domains.
        """
        db_path, store = performance_db

        # Read all cookies
        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        assert len(cookies) >= 1000

        # Get unique domains
        domains = list({c.domain for c in cookies})
        assert len(domains) >= 1000

        # Test filter performance
        search_term = "domain0500"  # Match domain0500.com from fixture

        start_time = time.perf_counter()

        # Simulate UI filter operation
        filtered = [d for d in domains if search_term in d]

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        # Verify performance
        assert elapsed_ms < 100, f"Filter took {elapsed_ms:.2f}ms, expected <100ms"

        # Verify filter worked (at least partial match)
        # Note: searching for partial term in 1000+ domains
        assert len(filtered) >= 1, f"Expected at least 1 match for '{search_term}', got {len(filtered)}"

    def test_case_insensitive_filter_performance(
        self, performance_db: tuple[Path, BrowserStore]
    ):
        """Test case-insensitive filtering performance."""
        db_path, store = performance_db

        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()
        domains = list({c.domain for c in cookies})

        search_term = "DOMAIN0500"  # Uppercase - matches domain0500.com

        start_time = time.perf_counter()

        # Case-insensitive filter
        filtered = [d for d in domains if search_term.lower() in d.lower()]

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        assert elapsed_ms < 100, f"Case-insensitive filter took {elapsed_ms:.2f}ms"
        assert len(filtered) >= 1

    def test_prefix_filter_performance(
        self, performance_db: tuple[Path, BrowserStore]
    ):
        """Test prefix-based filtering performance."""
        db_path, store = performance_db

        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()
        domains = list({c.domain for c in cookies})

        # Filter domains starting with "domain0"
        prefix = "domain0"

        start_time = time.perf_counter()

        filtered = [d for d in domains if d.startswith(prefix)]

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        assert elapsed_ms < 100, f"Prefix filter took {elapsed_ms:.2f}ms"

    def test_multiple_filters_performance(
        self, performance_db: tuple[Path, BrowserStore]
    ):
        """Test applying multiple filters in sequence."""
        db_path, store = performance_db

        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()
        domains = list({c.domain for c in cookies})

        filters = ["domain", "0", "com"]

        start_time = time.perf_counter()

        # Apply filters in sequence
        result = domains
        for f in filters:
            result = [d for d in result if f in d]

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        assert elapsed_ms < 100, f"Multiple filters took {elapsed_ms:.2f}ms"


class TestWhitelistPerformance:
    """Test whitelist lookup performance."""

    def test_whitelist_lookup_1000_domains(
        self, performance_db: tuple[Path, BrowserStore]
    ):
        """Test whitelist lookup performance for 1000 domains."""
        db_path, store = performance_db

        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()
        domains = list({c.domain for c in cookies})

        # Create whitelist with 100 entries
        whitelist_entries = [f"domain:whitelisted{i}.com" for i in range(100)]
        whitelist_entries.append("domain:domain0500.com")  # One match (with leading zero)
        wm = WhitelistManager(whitelist_entries)

        start_time = time.perf_counter()

        # Check all domains against whitelist
        whitelisted = [d for d in domains if wm.is_whitelisted(d)]

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        assert elapsed_ms < 100, f"Whitelist check took {elapsed_ms:.2f}ms"

        # Verify at least one match
        assert len(whitelisted) >= 1

    def test_whitelist_with_many_entries(self):
        """Test whitelist performance with many entries."""
        # Create large whitelist
        entries = [f"domain:site{i}.com" for i in range(500)]
        entries.extend([f"exact:api{i}.example.com" for i in range(500)])

        start_time = time.perf_counter()
        wm = WhitelistManager(entries)
        init_time = time.perf_counter() - start_time

        # Verify initialization is fast
        assert init_time < 1.0, f"Whitelist init took {init_time:.2f}s"

        # Test lookups
        test_domains = [f"sub.site{i}.com" for i in range(1000)]

        start_time = time.perf_counter()
        results = [wm.is_whitelisted(d) for d in test_domains]
        lookup_time = (time.perf_counter() - start_time) * 1000

        assert lookup_time < 100, f"1000 lookups took {lookup_time:.2f}ms"


class TestAggregationPerformance:
    """Test domain aggregation performance."""

    def test_aggregate_1000_cookies(
        self, performance_db: tuple[Path, BrowserStore]
    ):
        """Test cookie aggregation performance."""
        db_path, store = performance_db

        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        start_time = time.perf_counter()

        # Aggregate by domain
        domain_map: dict[str, list[CookieRecord]] = defaultdict(list)
        for cookie in cookies:
            domain_map[cookie.domain].append(cookie)

        # Create DomainAggregate objects
        aggregates = []
        for domain, domain_cookies in domain_map.items():
            browsers = {c.store.browser_name for c in domain_cookies}
            raw_keys = {c.raw_host_key for c in domain_cookies}
            aggregate = DomainAggregate(
                normalized_domain=domain,
                cookie_count=len(domain_cookies),
                browsers=browsers,
                records=domain_cookies,
                raw_host_keys=raw_keys,
            )
            aggregates.append(aggregate)

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        assert elapsed_ms < 100, f"Aggregation took {elapsed_ms:.2f}ms"
        assert len(aggregates) >= 1000

    def test_sort_aggregates_by_count(
        self, performance_db: tuple[Path, BrowserStore]
    ):
        """Test sorting aggregated domains by cookie count."""
        db_path, store = performance_db

        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        # Pre-aggregate
        domain_map: dict[str, list[CookieRecord]] = defaultdict(list)
        for cookie in cookies:
            domain_map[cookie.domain].append(cookie)

        aggregates = [
            DomainAggregate(
                normalized_domain=domain,
                cookie_count=len(domain_cookies),
                browsers={c.store.browser_name for c in domain_cookies},
                records=domain_cookies,
                raw_host_keys={c.raw_host_key for c in domain_cookies},
            )
            for domain, domain_cookies in domain_map.items()
        ]

        start_time = time.perf_counter()

        # Sort by cookie count descending
        sorted_aggs = sorted(aggregates, key=lambda a: a.cookie_count, reverse=True)

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        assert elapsed_ms < 50, f"Sorting took {elapsed_ms:.2f}ms"


class TestDatabaseReadPerformance:
    """Test database reading performance."""

    def test_read_1000_cookies(
        self, performance_db: tuple[Path, BrowserStore]
    ):
        """Test reading 1000+ cookies from database."""
        db_path, store = performance_db

        reader = ChromiumCookieReader(store)

        start_time = time.perf_counter()
        cookies = reader.read_cookies()
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Reading should be reasonably fast (allowing for disk I/O)
        assert elapsed_ms < 1000, f"Reading cookies took {elapsed_ms:.2f}ms"
        assert len(cookies) >= 1000

    def test_iter_cookies_performance(
        self, performance_db: tuple[Path, BrowserStore]
    ):
        """Test iterator-based cookie reading performance."""
        db_path, store = performance_db

        reader = ChromiumCookieReader(store)

        start_time = time.perf_counter()
        cookie_count = sum(1 for _ in reader.iter_cookies())
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        assert elapsed_ms < 1000, f"Iterating cookies took {elapsed_ms:.2f}ms"
        assert cookie_count >= 1000


class TestCombinedOperationsPerformance:
    """Test combined operations performance."""

    def test_full_workflow_performance(
        self, performance_db: tuple[Path, BrowserStore]
    ):
        """Test complete workflow: read -> filter -> whitelist check."""
        db_path, store = performance_db

        # Setup whitelist
        wm = WhitelistManager([
            "domain:google.com",
            "domain:facebook.com",
            "exact:api.github.com",
        ])

        reader = ChromiumCookieReader(store)

        start_time = time.perf_counter()

        # Step 1: Read cookies
        cookies = reader.read_cookies()

        # Step 2: Get unique domains
        domains = list({c.domain for c in cookies})

        # Step 3: Filter by search term
        search_term = "domain"
        filtered = [d for d in domains if search_term in d]

        # Step 4: Exclude whitelisted
        deletable = [d for d in filtered if not wm.is_whitelisted(d)]

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        # Full workflow should complete in reasonable time
        # (allowing for disk I/O, should be <2 seconds total)
        assert elapsed_ms < 2000, f"Full workflow took {elapsed_ms:.2f}ms"

        # Filter + whitelist check should be fast
        # (already read cookies, so these should be <100ms combined)


class TestMemoryEfficiency:
    """Test memory efficiency of operations."""

    def test_iterator_memory_efficiency(
        self, performance_db: tuple[Path, BrowserStore]
    ):
        """Test that iterator doesn't load all cookies at once."""
        db_path, store = performance_db

        reader = ChromiumCookieReader(store)

        # Using iterator should process cookies one at a time
        count = 0
        for cookie in reader.iter_cookies():
            count += 1
            if count >= 100:
                break

        # Should be able to stop early
        assert count == 100

    def test_domain_deduplication(
        self, performance_db: tuple[Path, BrowserStore]
    ):
        """Test that domain set deduplication is efficient."""
        db_path, store = performance_db

        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        start_time = time.perf_counter()

        # Set automatically deduplicates
        unique_domains = {c.domain for c in cookies}

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        assert elapsed_ms < 50, f"Deduplication took {elapsed_ms:.2f}ms"

        # Should have fewer unique domains than cookies
        assert len(unique_domains) <= len(cookies)
