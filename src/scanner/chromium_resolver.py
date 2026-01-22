"""Chromium-based browser profile resolver."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from src.core.models import BrowserStore
from src.scanner.browser_paths import BrowserConfig, CHROMIUM_SKIP_DIRS

logger = logging.getLogger(__name__)


class ChromiumProfileResolver:
    """Discovers profiles in Chromium-based browsers (Chrome, Edge, Brave, etc.)."""

    def __init__(self, config: BrowserConfig) -> None:
        self.config = config

    def discover(self) -> list[BrowserStore]:
        """Discover all profiles for this browser."""
        return list(self.iter_profiles())

    def iter_profiles(self) -> Iterator[BrowserStore]:
        """Yield BrowserStore for each valid profile."""
        user_data = self.config.user_data_path

        if not user_data.exists():
            logger.debug("%s User Data not found: %s", self.config.name, user_data)
            return

        local_state = user_data / "Local State"
        local_state_path = local_state if local_state.exists() else None

        for entry in user_data.iterdir():
            if not entry.is_dir():
                continue

            if not self._is_profile_dir(entry):
                continue

            cookie_db = self._find_cookie_db(entry)
            # Cookie db should exist since _is_profile_dir checks for it
            if cookie_db is None:
                continue

            yield BrowserStore(
                browser_name=self.config.name,
                profile_id=entry.name,
                db_path=cookie_db,
                is_chromium=True,
                local_state_path=local_state_path,
            )

    def _is_profile_dir(self, entry: Path) -> bool:
        """
        Check if directory represents a valid profile.

        Accepts any directory not in CHROMIUM_SKIP_DIRS that contains a cookie database.
        This supports custom profile names beyond just "Default" and "Profile N".

        Args:
            entry: Path to the potential profile directory

        Returns:
            True if this is a valid profile directory
        """
        if entry.name in CHROMIUM_SKIP_DIRS:
            return False

        # Verify it's a profile by checking for cookie database
        return self._find_cookie_db(entry) is not None

    def _find_cookie_db(self, profile_dir: Path) -> Path | None:
        """Find cookie database in profile directory."""
        # Modern Chromium (v96+): Network/Cookies
        modern_path = profile_dir / "Network" / "Cookies"
        if modern_path.exists():
            return modern_path

        # Legacy Chromium: Cookies in profile root
        legacy_path = profile_dir / "Cookies"
        if legacy_path.exists():
            return legacy_path

        return None
