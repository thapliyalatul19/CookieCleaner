"""Main profile resolver orchestrator."""

from __future__ import annotations

import logging
from typing import Iterator

from src.core.models import BrowserStore
from src.scanner.browser_paths import CHROMIUM_BROWSERS, BrowserConfig
from src.scanner.chromium_resolver import ChromiumProfileResolver
from src.scanner.firefox_resolver import FirefoxProfileResolver

logger = logging.getLogger(__name__)


class ProfileResolver:
    """Discovers browser profiles across all supported browsers."""

    def discover_all(self) -> list[BrowserStore]:
        """Discover all profiles across all browsers."""
        return list(self.iter_profiles())

    def iter_profiles(self) -> Iterator[BrowserStore]:
        """Yield profiles from all browser resolvers."""
        # Chromium-based browsers
        for config in CHROMIUM_BROWSERS:
            resolver = ChromiumProfileResolver(config)
            yield from resolver.iter_profiles()

        # Firefox
        firefox_resolver = FirefoxProfileResolver()
        yield from firefox_resolver.iter_profiles()

    def discover_browser(self, name: str) -> list[BrowserStore]:
        """Discover profiles for a specific browser by name."""
        name_lower = name.lower()

        # Check Chromium browsers
        for config in CHROMIUM_BROWSERS:
            if config.name.lower() == name_lower:
                return ChromiumProfileResolver(config).discover()

        # Check Firefox
        if name_lower == "firefox":
            return FirefoxProfileResolver().discover()

        logger.warning("Unknown browser: %s", name)
        return []

    def get_browser_config(self, name: str) -> BrowserConfig | None:
        """Get browser configuration by name."""
        name_lower = name.lower()

        for config in CHROMIUM_BROWSERS:
            if config.name.lower() == name_lower:
                return config

        if name_lower == "firefox":
            from src.scanner.browser_paths import FIREFOX_CONFIG
            return FIREFOX_CONFIG

        return None
