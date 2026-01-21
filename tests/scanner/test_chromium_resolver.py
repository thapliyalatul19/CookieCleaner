"""Tests for Chromium profile resolver."""

import pytest
from pathlib import Path

from src.scanner.browser_paths import BrowserConfig
from src.scanner.chromium_resolver import ChromiumProfileResolver


class TestChromiumProfileResolver:
    """Tests for ChromiumProfileResolver."""

    def test_discover_profiles_with_mock_data(
        self, mock_chromium_user_data: Path
    ) -> None:
        """Should discover Default and Profile 1."""
        config = BrowserConfig(
            name="TestChrome",
            user_data_path=mock_chromium_user_data,
            is_chromium=True,
            executable_name="chrome.exe",
        )
        resolver = ChromiumProfileResolver(config)
        profiles = resolver.discover()

        assert len(profiles) == 2

        profile_ids = {p.profile_id for p in profiles}
        assert "Default" in profile_ids
        assert "Profile 1" in profile_ids

    def test_skips_non_profile_directories(
        self, mock_chromium_user_data: Path
    ) -> None:
        """Should skip Crashpad, Safe Browsing, etc."""
        config = BrowserConfig(
            name="TestChrome",
            user_data_path=mock_chromium_user_data,
            is_chromium=True,
            executable_name="chrome.exe",
        )
        resolver = ChromiumProfileResolver(config)
        profiles = resolver.discover()

        profile_ids = {p.profile_id for p in profiles}
        assert "Crashpad" not in profile_ids
        assert "Safe Browsing" not in profile_ids
        assert "ShaderCache" not in profile_ids

    def test_finds_modern_cookie_path(
        self, mock_chromium_user_data: Path
    ) -> None:
        """Should find Network/Cookies for modern Chromium."""
        config = BrowserConfig(
            name="TestChrome",
            user_data_path=mock_chromium_user_data,
            is_chromium=True,
            executable_name="chrome.exe",
        )
        resolver = ChromiumProfileResolver(config)
        profiles = resolver.discover()

        default_profile = next(p for p in profiles if p.profile_id == "Default")
        assert "Network" in str(default_profile.db_path)
        assert default_profile.db_path.name == "Cookies"

    def test_finds_legacy_cookie_path(
        self, mock_chromium_user_data: Path
    ) -> None:
        """Should find Cookies in profile root for legacy Chromium."""
        config = BrowserConfig(
            name="TestChrome",
            user_data_path=mock_chromium_user_data,
            is_chromium=True,
            executable_name="chrome.exe",
        )
        resolver = ChromiumProfileResolver(config)
        profiles = resolver.discover()

        profile1 = next(p for p in profiles if p.profile_id == "Profile 1")
        assert "Network" not in str(profile1.db_path)
        assert profile1.db_path.name == "Cookies"

    def test_includes_local_state_path(
        self, mock_chromium_user_data: Path
    ) -> None:
        """Should include Local State path for DPAPI."""
        config = BrowserConfig(
            name="TestChrome",
            user_data_path=mock_chromium_user_data,
            is_chromium=True,
            executable_name="chrome.exe",
        )
        resolver = ChromiumProfileResolver(config)
        profiles = resolver.discover()

        for profile in profiles:
            assert profile.local_state_path is not None
            assert profile.local_state_path.name == "Local State"

    def test_handles_missing_user_data(self, tmp_path: Path) -> None:
        """Should return empty list if User Data doesn't exist."""
        config = BrowserConfig(
            name="TestChrome",
            user_data_path=tmp_path / "NonExistent",
            is_chromium=True,
            executable_name="chrome.exe",
        )
        resolver = ChromiumProfileResolver(config)
        profiles = resolver.discover()

        assert profiles == []

    def test_skips_profile_without_cookies(self, tmp_path: Path) -> None:
        """Should skip profiles that don't have a cookie database."""
        user_data = tmp_path / "User Data"
        user_data.mkdir()

        # Create profile without cookies
        empty_profile = user_data / "Default"
        empty_profile.mkdir()

        config = BrowserConfig(
            name="TestChrome",
            user_data_path=user_data,
            is_chromium=True,
            executable_name="chrome.exe",
        )
        resolver = ChromiumProfileResolver(config)
        profiles = resolver.discover()

        assert profiles == []

    def test_browser_store_attributes(
        self, mock_chromium_user_data: Path
    ) -> None:
        """BrowserStore should have correct attributes."""
        config = BrowserConfig(
            name="TestChrome",
            user_data_path=mock_chromium_user_data,
            is_chromium=True,
            executable_name="chrome.exe",
        )
        resolver = ChromiumProfileResolver(config)
        profiles = resolver.discover()

        default_profile = next(p for p in profiles if p.profile_id == "Default")
        assert default_profile.browser_name == "TestChrome"
        assert default_profile.is_chromium is True
        assert default_profile.db_path.exists()
