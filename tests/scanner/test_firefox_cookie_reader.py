"""Tests for Firefox cookie reader."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.core.models import BrowserStore
from src.scanner.firefox_cookie_reader import (
    FirefoxCookieReader,
    firefox_time_to_datetime,
    normalize_domain,
)


class TestFirefoxTimeConversion:
    """Tests for Firefox timestamp conversion."""

    def test_converts_valid_timestamp(self) -> None:
        """Converts Unix seconds to datetime."""
        # 2024-01-01 00:00:00 UTC
        unix_time = 1704067200

        result = firefox_time_to_datetime(unix_time)

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
        assert result.tzinfo == timezone.utc

    def test_returns_none_for_zero(self) -> None:
        """Session cookies have expiry=0, should return None."""
        result = firefox_time_to_datetime(0)
        assert result is None

    def test_handles_invalid_timestamp(self) -> None:
        """Invalid/overflow timestamps return None instead of raising."""
        # Extremely large value that would overflow
        result = firefox_time_to_datetime(999999999999999)
        assert result is None


class TestNormalizeDomain:
    """Tests for domain normalization."""

    def test_strips_leading_dot(self) -> None:
        """Removes leading dot from domain."""
        assert normalize_domain(".mozilla.org") == "mozilla.org"

    def test_handles_no_leading_dot(self) -> None:
        """Domains without leading dot are unchanged."""
        assert normalize_domain("addons.mozilla.org") == "addons.mozilla.org"


class TestFirefoxCookieReader:
    """Tests for FirefoxCookieReader class."""

    def test_reads_all_cookies(self, firefox_store: BrowserStore) -> None:
        """Reads all cookies from Firefox database."""
        reader = FirefoxCookieReader(firefox_store)
        cookies = reader.read_cookies()

        assert len(cookies) == 4
        assert all(c.store is firefox_store for c in cookies)

    def test_cookie_domains_normalized(self, firefox_store: BrowserStore) -> None:
        """Cookie domains have leading dots stripped."""
        reader = FirefoxCookieReader(firefox_store)
        cookies = reader.read_cookies()

        # .mozilla.org should be normalized
        moz_cookies = [c for c in cookies if c.domain == "mozilla.org"]
        assert len(moz_cookies) == 2  # mozilla.org and .mozilla.org

        for cookie in moz_cookies:
            assert not cookie.domain.startswith(".")

    def test_preserves_raw_host_key(self, firefox_store: BrowserStore) -> None:
        """Raw host is preserved for SQL queries."""
        reader = FirefoxCookieReader(firefox_store)
        cookies = reader.read_cookies()

        # Find the cookie that had a leading dot
        tracking_cookie = next(c for c in cookies if c.name == "tracking_id")
        assert tracking_cookie.raw_host_key == ".mozilla.org"

    def test_handles_session_cookies(self, firefox_store: BrowserStore) -> None:
        """Session cookies (expiry=0) have None expiry."""
        reader = FirefoxCookieReader(firefox_store)
        cookies = reader.read_cookies()

        reddit_cookie = next(c for c in cookies if "reddit" in c.domain)
        assert reddit_cookie.expires is None

    def test_handles_secure_flag(self, firefox_store: BrowserStore) -> None:
        """isSecure flag is correctly read."""
        reader = FirefoxCookieReader(firefox_store)
        cookies = reader.read_cookies()

        # session cookie at mozilla.org is secure
        session_cookie = next(c for c in cookies if c.name == "session")
        assert session_cookie.is_secure is True

        # tracking_id cookie is not secure
        tracking_cookie = next(c for c in cookies if c.name == "tracking_id")
        assert tracking_cookie.is_secure is False

    def test_iter_cookies_yields_same_as_read(self, firefox_store: BrowserStore) -> None:
        """iter_cookies yields same cookies as read_cookies."""
        reader = FirefoxCookieReader(firefox_store)

        read_result = reader.read_cookies()
        iter_result = list(reader.iter_cookies())

        assert len(read_result) == len(iter_result)

    def test_handles_missing_database(self, tmp_path: Path) -> None:
        """Returns empty list for missing database."""
        store = BrowserStore(
            browser_name="Firefox",
            profile_id="default",
            db_path=tmp_path / "nonexistent" / "cookies.sqlite",
            is_chromium=False,
        )
        reader = FirefoxCookieReader(store)
        cookies = reader.read_cookies()

        assert cookies == []

    def test_handles_corrupted_database(self, mock_corrupted_db: Path) -> None:
        """Returns empty list for corrupted database."""
        store = BrowserStore(
            browser_name="Firefox",
            profile_id="default",
            db_path=mock_corrupted_db,
            is_chromium=False,
        )
        reader = FirefoxCookieReader(store)
        cookies = reader.read_cookies()

        assert cookies == []

    def test_handles_wrong_table_name(self, tmp_path: Path) -> None:
        """Returns empty list when moz_cookies table doesn't exist."""
        import sqlite3

        db_path = tmp_path / "WrongTable.sqlite"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE other_table (id INTEGER)")
        conn.close()

        store = BrowserStore(
            browser_name="Firefox",
            profile_id="default",
            db_path=db_path,
            is_chromium=False,
        )
        reader = FirefoxCookieReader(store)
        cookies = reader.read_cookies()

        assert cookies == []

    def test_handles_empty_database(self, tmp_path: Path) -> None:
        """Returns empty list for database with no cookies."""
        import sqlite3

        db_path = tmp_path / "empty.sqlite"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE moz_cookies (
                id INTEGER PRIMARY KEY,
                originAttributes TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL,
                value TEXT NOT NULL,
                host TEXT NOT NULL,
                path TEXT NOT NULL DEFAULT '/',
                expiry INTEGER NOT NULL,
                lastAccessed INTEGER NOT NULL,
                creationTime INTEGER NOT NULL,
                isSecure INTEGER NOT NULL DEFAULT 0,
                isHttpOnly INTEGER NOT NULL DEFAULT 0,
                inBrowserElement INTEGER NOT NULL DEFAULT 0,
                sameSite INTEGER NOT NULL DEFAULT 0,
                rawSameSite INTEGER NOT NULL DEFAULT 0,
                schemeMap INTEGER NOT NULL DEFAULT 0,
                isPartitionedAttributeSet INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.close()

        store = BrowserStore(
            browser_name="Firefox",
            profile_id="default",
            db_path=db_path,
            is_chromium=False,
        )
        reader = FirefoxCookieReader(store)
        cookies = reader.read_cookies()

        assert cookies == []
