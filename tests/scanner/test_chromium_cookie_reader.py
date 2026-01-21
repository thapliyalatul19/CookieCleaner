"""Tests for Chromium cookie reader."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.core.models import BrowserStore
from src.scanner.chromium_cookie_reader import (
    ChromiumCookieReader,
    chromium_time_to_datetime,
    normalize_domain,
    CHROMIUM_EPOCH_OFFSET,
)


class TestChromiumTimeConversion:
    """Tests for Chromium timestamp conversion."""

    def test_converts_valid_timestamp(self) -> None:
        """Converts Chromium microseconds to datetime."""
        # 2024-01-01 00:00:00 UTC = Unix 1704067200
        # Chromium time = (1704067200 + 11644473600) * 1_000_000
        chromium_time = (1704067200 + CHROMIUM_EPOCH_OFFSET) * 1_000_000

        result = chromium_time_to_datetime(chromium_time)

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
        assert result.tzinfo == timezone.utc

    def test_returns_none_for_zero(self) -> None:
        """Session cookies have expires_utc=0, should return None."""
        result = chromium_time_to_datetime(0)
        assert result is None

    def test_handles_invalid_timestamp(self) -> None:
        """Invalid/overflow timestamps return None instead of raising."""
        # Extremely large value that would overflow
        result = chromium_time_to_datetime(999999999999999999999)
        assert result is None


class TestNormalizeDomain:
    """Tests for domain normalization."""

    def test_strips_leading_dot(self) -> None:
        """Removes leading dot from domain."""
        assert normalize_domain(".google.com") == "google.com"
        assert normalize_domain(".facebook.com") == "facebook.com"

    def test_handles_no_leading_dot(self) -> None:
        """Domains without leading dot are unchanged."""
        assert normalize_domain("accounts.google.com") == "accounts.google.com"
        assert normalize_domain("example.com") == "example.com"

    def test_handles_multiple_leading_dots(self) -> None:
        """Multiple leading dots are all stripped."""
        assert normalize_domain("..weird.domain.com") == "weird.domain.com"


class TestChromiumCookieReader:
    """Tests for ChromiumCookieReader class."""

    def test_reads_all_cookies(self, chromium_store: BrowserStore) -> None:
        """Reads all cookies from Chromium database."""
        reader = ChromiumCookieReader(chromium_store)
        cookies = reader.read_cookies()

        assert len(cookies) == 7
        assert all(c.store is chromium_store for c in cookies)

    def test_cookie_domains_normalized(self, chromium_store: BrowserStore) -> None:
        """Cookie domains have leading dots stripped."""
        reader = ChromiumCookieReader(chromium_store)
        cookies = reader.read_cookies()

        google_cookies = [c for c in cookies if "google" in c.domain]
        assert len(google_cookies) == 3

        # Check domain is normalized (no leading dot)
        for cookie in google_cookies:
            assert not cookie.domain.startswith(".")

    def test_preserves_raw_host_key(self, chromium_store: BrowserStore) -> None:
        """Raw host_key is preserved for SQL queries."""
        reader = ChromiumCookieReader(chromium_store)
        cookies = reader.read_cookies()

        # Find cookies that had leading dots
        google_domain_cookies = [c for c in cookies if c.domain == "google.com"]
        assert len(google_domain_cookies) == 2
        assert all(c.raw_host_key == ".google.com" for c in google_domain_cookies)

    def test_handles_session_cookies(self, chromium_store: BrowserStore) -> None:
        """Session cookies (expires=0) have None expiry."""
        reader = ChromiumCookieReader(chromium_store)
        cookies = reader.read_cookies()

        github_cookie = next(c for c in cookies if "github" in c.domain)
        assert github_cookie.expires is None

    def test_handles_secure_flag(self, chromium_store: BrowserStore) -> None:
        """is_secure flag is correctly read."""
        reader = ChromiumCookieReader(chromium_store)
        cookies = reader.read_cookies()

        # Google cookies are secure
        google_cookie = next(c for c in cookies if c.raw_host_key == ".google.com")
        assert google_cookie.is_secure is True

        # example.com cookie is not secure
        example_cookie = next(c for c in cookies if c.domain == "example.com")
        assert example_cookie.is_secure is False

    def test_handles_edge_22_column_schema(self, edge_store: BrowserStore) -> None:
        """Reads Edge database with 22 columns via dynamic detection."""
        reader = ChromiumCookieReader(edge_store)
        cookies = reader.read_cookies()

        assert len(cookies) == 2
        domains = {c.domain for c in cookies}
        assert "microsoft.com" in domains
        assert "bing.com" in domains

    def test_iter_cookies_yields_same_as_read(self, chromium_store: BrowserStore) -> None:
        """iter_cookies yields same cookies as read_cookies."""
        reader = ChromiumCookieReader(chromium_store)

        read_result = reader.read_cookies()
        iter_result = list(reader.iter_cookies())

        assert len(read_result) == len(iter_result)

    def test_handles_missing_database(self, tmp_path: Path) -> None:
        """Returns empty list for missing database."""
        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Default",
            db_path=tmp_path / "nonexistent" / "Cookies",
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        assert cookies == []

    def test_handles_empty_database(self, mock_empty_chromium_db: Path) -> None:
        """Returns empty list for database with no cookies."""
        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Default",
            db_path=mock_empty_chromium_db,
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        assert cookies == []

    def test_handles_corrupted_database(self, mock_corrupted_db: Path) -> None:
        """Returns empty list for corrupted database."""
        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Default",
            db_path=mock_corrupted_db,
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        assert cookies == []

    def test_handles_wrong_table_name(self, tmp_path: Path) -> None:
        """Returns empty list when cookies table doesn't exist."""
        import sqlite3

        db_path = tmp_path / "WrongTable"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE other_table (id INTEGER)")
        conn.close()

        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Default",
            db_path=db_path,
            is_chromium=True,
        )
        reader = ChromiumCookieReader(store)
        cookies = reader.read_cookies()

        assert cookies == []
