"""Tests for browser path constants."""

import pytest
from pathlib import Path

from src.scanner.browser_paths import (
    BrowserConfig,
    CHROME_CONFIG,
    EDGE_CONFIG,
    BRAVE_CONFIG,
    OPERA_CONFIG,
    VIVALDI_CONFIG,
    FIREFOX_CONFIG,
    CHROMIUM_BROWSERS,
    ALL_BROWSERS,
    CHROMIUM_SKIP_DIRS,
)


class TestBrowserConfig:
    """Tests for BrowserConfig dataclass."""

    def test_browser_config_is_frozen(self) -> None:
        """BrowserConfig should be immutable."""
        config = BrowserConfig(
            name="Test",
            user_data_path=Path("C:/test"),
            is_chromium=True,
            executable_name="test.exe",
        )
        with pytest.raises(AttributeError):
            config.name = "Modified"  # type: ignore

    def test_browser_config_equality(self) -> None:
        """BrowserConfig instances with same values should be equal."""
        config1 = BrowserConfig(
            name="Test",
            user_data_path=Path("C:/test"),
            is_chromium=True,
            executable_name="test.exe",
        )
        config2 = BrowserConfig(
            name="Test",
            user_data_path=Path("C:/test"),
            is_chromium=True,
            executable_name="test.exe",
        )
        assert config1 == config2


class TestChromiumBrowserConfigs:
    """Tests for Chromium browser configurations."""

    def test_chrome_config(self) -> None:
        """Chrome config should have correct values."""
        assert CHROME_CONFIG.name == "Chrome"
        assert CHROME_CONFIG.is_chromium is True
        assert CHROME_CONFIG.executable_name == "chrome.exe"
        assert "Google" in str(CHROME_CONFIG.user_data_path)

    def test_edge_config(self) -> None:
        """Edge config should have correct values."""
        assert EDGE_CONFIG.name == "Edge"
        assert EDGE_CONFIG.is_chromium is True
        assert EDGE_CONFIG.executable_name == "msedge.exe"
        assert "Microsoft" in str(EDGE_CONFIG.user_data_path)

    def test_brave_config(self) -> None:
        """Brave config should have correct values."""
        assert BRAVE_CONFIG.name == "Brave"
        assert BRAVE_CONFIG.is_chromium is True
        assert BRAVE_CONFIG.executable_name == "brave.exe"

    def test_opera_config(self) -> None:
        """Opera config should have correct values."""
        assert OPERA_CONFIG.name == "Opera"
        assert OPERA_CONFIG.is_chromium is True
        assert OPERA_CONFIG.executable_name == "opera.exe"

    def test_vivaldi_config(self) -> None:
        """Vivaldi config should have correct values."""
        assert VIVALDI_CONFIG.name == "Vivaldi"
        assert VIVALDI_CONFIG.is_chromium is True
        assert VIVALDI_CONFIG.executable_name == "vivaldi.exe"

    def test_chromium_browsers_tuple(self) -> None:
        """CHROMIUM_BROWSERS should contain all Chromium configs."""
        assert CHROME_CONFIG in CHROMIUM_BROWSERS
        assert EDGE_CONFIG in CHROMIUM_BROWSERS
        assert BRAVE_CONFIG in CHROMIUM_BROWSERS
        assert OPERA_CONFIG in CHROMIUM_BROWSERS
        assert VIVALDI_CONFIG in CHROMIUM_BROWSERS
        assert FIREFOX_CONFIG not in CHROMIUM_BROWSERS


class TestFirefoxConfig:
    """Tests for Firefox configuration."""

    def test_firefox_config(self) -> None:
        """Firefox config should have correct values."""
        assert FIREFOX_CONFIG.name == "Firefox"
        assert FIREFOX_CONFIG.is_chromium is False
        assert FIREFOX_CONFIG.executable_name == "firefox.exe"
        assert "Mozilla" in str(FIREFOX_CONFIG.user_data_path)


class TestAllBrowsers:
    """Tests for ALL_BROWSERS collection."""

    def test_all_browsers_includes_chromium_and_firefox(self) -> None:
        """ALL_BROWSERS should include all supported browsers."""
        assert len(ALL_BROWSERS) == 6
        assert FIREFOX_CONFIG in ALL_BROWSERS
        for config in CHROMIUM_BROWSERS:
            assert config in ALL_BROWSERS


class TestChromiumSkipDirs:
    """Tests for CHROMIUM_SKIP_DIRS."""

    def test_skip_dirs_contains_expected_entries(self) -> None:
        """Skip dirs should include common non-profile directories."""
        assert "Crashpad" in CHROMIUM_SKIP_DIRS
        assert "Safe Browsing" in CHROMIUM_SKIP_DIRS
        assert "ShaderCache" in CHROMIUM_SKIP_DIRS

    def test_skip_dirs_does_not_contain_default(self) -> None:
        """Skip dirs should NOT include Default profile."""
        assert "Default" not in CHROMIUM_SKIP_DIRS
