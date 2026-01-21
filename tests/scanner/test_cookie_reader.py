"""Tests for cookie reader factory and base interface."""

import pytest

from src.core.models import BrowserStore
from src.scanner import (
    BaseCookieReader,
    ChromiumCookieReader,
    FirefoxCookieReader,
    create_reader,
)


class TestCreateReaderFactory:
    """Tests for the create_reader factory function."""

    def test_creates_chromium_reader_for_chromium_store(self, chromium_store: BrowserStore) -> None:
        """Factory returns ChromiumCookieReader for Chromium-based browsers."""
        reader = create_reader(chromium_store)

        assert isinstance(reader, ChromiumCookieReader)
        assert isinstance(reader, BaseCookieReader)
        assert reader.store is chromium_store

    def test_creates_chromium_reader_for_edge_store(self, edge_store: BrowserStore) -> None:
        """Factory returns ChromiumCookieReader for Edge (also Chromium-based)."""
        reader = create_reader(edge_store)

        assert isinstance(reader, ChromiumCookieReader)

    def test_creates_firefox_reader_for_firefox_store(self, firefox_store: BrowserStore) -> None:
        """Factory returns FirefoxCookieReader for Firefox browser."""
        reader = create_reader(firefox_store)

        assert isinstance(reader, FirefoxCookieReader)
        assert isinstance(reader, BaseCookieReader)
        assert reader.store is firefox_store


class TestIntegration:
    """Integration tests using the factory with real mock databases."""

    def test_read_chromium_cookies_via_factory(self, chromium_store: BrowserStore) -> None:
        """Factory-created reader successfully reads Chromium cookies."""
        reader = create_reader(chromium_store)
        cookies = reader.read_cookies()

        assert len(cookies) == 7  # 7 test cookies in fixture
        domains = {c.domain for c in cookies}
        assert "google.com" in domains
        assert "facebook.com" in domains

    def test_read_firefox_cookies_via_factory(self, firefox_store: BrowserStore) -> None:
        """Factory-created reader successfully reads Firefox cookies."""
        reader = create_reader(firefox_store)
        cookies = reader.read_cookies()

        assert len(cookies) == 4  # 4 test cookies in fixture
        domains = {c.domain for c in cookies}
        assert "mozilla.org" in domains
        assert "reddit.com" in domains
