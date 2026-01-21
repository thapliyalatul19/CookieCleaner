"""Tests for main ProfileResolver orchestrator."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.scanner.profile_resolver import ProfileResolver
from src.scanner.browser_paths import CHROME_CONFIG, FIREFOX_CONFIG
from src.core.models import BrowserStore


class TestProfileResolver:
    """Tests for ProfileResolver."""

    def test_discover_all_combines_browsers(self) -> None:
        """Should combine profiles from all browsers."""
        mock_chrome_profiles = [
            BrowserStore(
                browser_name="Chrome",
                profile_id="Default",
                db_path=Path("C:/chrome/cookies"),
                is_chromium=True,
                local_state_path=Path("C:/chrome/Local State"),
            )
        ]
        mock_firefox_profiles = [
            BrowserStore(
                browser_name="Firefox",
                profile_id="default-release",
                db_path=Path("C:/firefox/cookies.sqlite"),
                is_chromium=False,
                local_state_path=None,
            )
        ]

        with patch(
            "src.scanner.profile_resolver.ChromiumProfileResolver"
        ) as MockChromium, patch(
            "src.scanner.profile_resolver.FirefoxProfileResolver"
        ) as MockFirefox:
            # Setup mock returns
            MockChromium.return_value.iter_profiles.return_value = iter(
                mock_chrome_profiles
            )
            MockFirefox.return_value.iter_profiles.return_value = iter(
                mock_firefox_profiles
            )

            resolver = ProfileResolver()
            profiles = resolver.discover_all()

        # Should have profiles from both browsers
        browser_names = {p.browser_name for p in profiles}
        assert "Chrome" in browser_names
        assert "Firefox" in browser_names

    def test_discover_browser_chrome(self) -> None:
        """Should discover only Chrome profiles."""
        mock_profiles = [
            BrowserStore(
                browser_name="Chrome",
                profile_id="Default",
                db_path=Path("C:/chrome/cookies"),
                is_chromium=True,
                local_state_path=Path("C:/chrome/Local State"),
            )
        ]

        with patch(
            "src.scanner.profile_resolver.ChromiumProfileResolver"
        ) as MockChromium:
            MockChromium.return_value.discover.return_value = mock_profiles

            resolver = ProfileResolver()
            profiles = resolver.discover_browser("Chrome")

        assert len(profiles) == 1
        assert profiles[0].browser_name == "Chrome"

    def test_discover_browser_firefox(self) -> None:
        """Should discover only Firefox profiles."""
        mock_profiles = [
            BrowserStore(
                browser_name="Firefox",
                profile_id="default-release",
                db_path=Path("C:/firefox/cookies.sqlite"),
                is_chromium=False,
                local_state_path=None,
            )
        ]

        with patch(
            "src.scanner.profile_resolver.FirefoxProfileResolver"
        ) as MockFirefox:
            MockFirefox.return_value.discover.return_value = mock_profiles

            resolver = ProfileResolver()
            profiles = resolver.discover_browser("Firefox")

        assert len(profiles) == 1
        assert profiles[0].browser_name == "Firefox"

    def test_discover_browser_case_insensitive(self) -> None:
        """Browser name lookup should be case-insensitive."""
        mock_profiles = [
            BrowserStore(
                browser_name="Chrome",
                profile_id="Default",
                db_path=Path("C:/chrome/cookies"),
                is_chromium=True,
                local_state_path=None,
            )
        ]

        with patch(
            "src.scanner.profile_resolver.ChromiumProfileResolver"
        ) as MockChromium:
            MockChromium.return_value.discover.return_value = mock_profiles

            resolver = ProfileResolver()

            profiles_lower = resolver.discover_browser("chrome")
            profiles_upper = resolver.discover_browser("CHROME")
            profiles_mixed = resolver.discover_browser("ChRoMe")

        assert len(profiles_lower) == 1
        assert len(profiles_upper) == 1
        assert len(profiles_mixed) == 1

    def test_discover_browser_unknown(self) -> None:
        """Should return empty list for unknown browser."""
        resolver = ProfileResolver()
        profiles = resolver.discover_browser("UnknownBrowser")

        assert profiles == []

    def test_get_browser_config_chrome(self) -> None:
        """Should return Chrome config."""
        resolver = ProfileResolver()
        config = resolver.get_browser_config("Chrome")

        assert config is not None
        assert config.name == "Chrome"
        assert config.is_chromium is True

    def test_get_browser_config_firefox(self) -> None:
        """Should return Firefox config."""
        resolver = ProfileResolver()
        config = resolver.get_browser_config("Firefox")

        assert config is not None
        assert config.name == "Firefox"
        assert config.is_chromium is False

    def test_get_browser_config_unknown(self) -> None:
        """Should return None for unknown browser."""
        resolver = ProfileResolver()
        config = resolver.get_browser_config("UnknownBrowser")

        assert config is None

    def test_iter_profiles_is_lazy(self) -> None:
        """iter_profiles should yield profiles lazily."""
        with patch(
            "src.scanner.profile_resolver.ChromiumProfileResolver"
        ) as MockChromium, patch(
            "src.scanner.profile_resolver.FirefoxProfileResolver"
        ) as MockFirefox:
            MockChromium.return_value.iter_profiles.return_value = iter([])
            MockFirefox.return_value.iter_profiles.return_value = iter([])

            resolver = ProfileResolver()
            iterator = resolver.iter_profiles()

            # Should return iterator, not list
            assert hasattr(iterator, "__next__")
