"""Tests for Firefox profile resolver."""

import pytest
from pathlib import Path
from unittest.mock import patch

from src.scanner.firefox_resolver import FirefoxProfileResolver
from src.scanner.browser_paths import FIREFOX_CONFIG, BrowserConfig


class TestFirefoxProfileResolver:
    """Tests for FirefoxProfileResolver."""

    def test_discover_profiles_with_mock_data(
        self, mock_firefox_root: Path
    ) -> None:
        """Should discover profiles from profiles.ini."""
        # Patch FIREFOX_CONFIG to use mock path
        mock_config = BrowserConfig(
            name="Firefox",
            user_data_path=mock_firefox_root,
            is_chromium=False,
            executable_name="firefox.exe",
        )

        with patch.object(FirefoxProfileResolver, "__init__", lambda self: None):
            resolver = FirefoxProfileResolver()
            resolver.config = mock_config
            profiles = resolver.discover()

        assert len(profiles) == 2

        profile_ids = {p.profile_id for p in profiles}
        assert "abc123.default" in profile_ids
        assert "xyz789.dev" in profile_ids

    def test_handles_relative_paths(self, mock_firefox_root: Path) -> None:
        """Should resolve relative paths correctly."""
        mock_config = BrowserConfig(
            name="Firefox",
            user_data_path=mock_firefox_root,
            is_chromium=False,
            executable_name="firefox.exe",
        )

        with patch.object(FirefoxProfileResolver, "__init__", lambda self: None):
            resolver = FirefoxProfileResolver()
            resolver.config = mock_config
            profiles = resolver.discover()

        for profile in profiles:
            assert profile.db_path.exists()
            assert profile.db_path.name == "cookies.sqlite"

    def test_handles_absolute_paths(
        self, mock_firefox_absolute_path: Path, tmp_path: Path
    ) -> None:
        """Should handle absolute paths in profiles.ini."""
        mock_config = BrowserConfig(
            name="Firefox",
            user_data_path=mock_firefox_absolute_path,
            is_chromium=False,
            executable_name="firefox.exe",
        )

        with patch.object(FirefoxProfileResolver, "__init__", lambda self: None):
            resolver = FirefoxProfileResolver()
            resolver.config = mock_config
            profiles = resolver.discover()

        assert len(profiles) == 1
        assert profiles[0].profile_id == "myprofile"
        assert profiles[0].db_path.exists()

    def test_skips_profiles_without_cookies(
        self, mock_firefox_no_cookies: Path
    ) -> None:
        """Should skip profiles without cookies.sqlite."""
        mock_config = BrowserConfig(
            name="Firefox",
            user_data_path=mock_firefox_no_cookies,
            is_chromium=False,
            executable_name="firefox.exe",
        )

        with patch.object(FirefoxProfileResolver, "__init__", lambda self: None):
            resolver = FirefoxProfileResolver()
            resolver.config = mock_config
            profiles = resolver.discover()

        assert profiles == []

    def test_handles_missing_firefox_root(self, tmp_path: Path) -> None:
        """Should return empty list if Firefox not installed."""
        mock_config = BrowserConfig(
            name="Firefox",
            user_data_path=tmp_path / "NonExistent",
            is_chromium=False,
            executable_name="firefox.exe",
        )

        with patch.object(FirefoxProfileResolver, "__init__", lambda self: None):
            resolver = FirefoxProfileResolver()
            resolver.config = mock_config
            profiles = resolver.discover()

        assert profiles == []

    def test_handles_missing_profiles_ini(self, tmp_path: Path) -> None:
        """Should return empty list if profiles.ini doesn't exist."""
        firefox_root = tmp_path / "Mozilla" / "Firefox"
        firefox_root.mkdir(parents=True)

        mock_config = BrowserConfig(
            name="Firefox",
            user_data_path=firefox_root,
            is_chromium=False,
            executable_name="firefox.exe",
        )

        with patch.object(FirefoxProfileResolver, "__init__", lambda self: None):
            resolver = FirefoxProfileResolver()
            resolver.config = mock_config
            profiles = resolver.discover()

        assert profiles == []

    def test_browser_store_attributes(self, mock_firefox_root: Path) -> None:
        """BrowserStore should have correct Firefox attributes."""
        mock_config = BrowserConfig(
            name="Firefox",
            user_data_path=mock_firefox_root,
            is_chromium=False,
            executable_name="firefox.exe",
        )

        with patch.object(FirefoxProfileResolver, "__init__", lambda self: None):
            resolver = FirefoxProfileResolver()
            resolver.config = mock_config
            profiles = resolver.discover()

        for profile in profiles:
            assert profile.browser_name == "Firefox"
            assert profile.is_chromium is False
            assert profile.local_state_path is None

    def test_handles_malformed_profiles_ini(self, tmp_path: Path) -> None:
        """Should handle malformed profiles.ini gracefully."""
        firefox_root = tmp_path / "Mozilla" / "Firefox"
        firefox_root.mkdir(parents=True)

        # Create malformed profiles.ini
        profiles_ini = firefox_root / "profiles.ini"
        profiles_ini.write_text("[Profile0\nMissingClosingBracket")

        mock_config = BrowserConfig(
            name="Firefox",
            user_data_path=firefox_root,
            is_chromium=False,
            executable_name="firefox.exe",
        )

        with patch.object(FirefoxProfileResolver, "__init__", lambda self: None):
            resolver = FirefoxProfileResolver()
            resolver.config = mock_config
            profiles = resolver.discover()

        # Should return empty list, not crash
        assert profiles == []
