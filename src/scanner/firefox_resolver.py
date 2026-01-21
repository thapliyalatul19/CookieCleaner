"""Firefox browser profile resolver."""

from __future__ import annotations

import configparser
import logging
from pathlib import Path
from typing import Iterator

from src.core.models import BrowserStore
from src.scanner.browser_paths import FIREFOX_CONFIG

logger = logging.getLogger(__name__)


class FirefoxProfileResolver:
    """Discovers Firefox profiles via profiles.ini parsing."""

    def __init__(self) -> None:
        self.config = FIREFOX_CONFIG

    def discover(self) -> list[BrowserStore]:
        """Discover all Firefox profiles."""
        return list(self.iter_profiles())

    def iter_profiles(self) -> Iterator[BrowserStore]:
        """Yield BrowserStore for each valid Firefox profile."""
        firefox_root = self.config.user_data_path

        if not firefox_root.exists():
            logger.debug("Firefox root not found: %s", firefox_root)
            return

        profiles_ini = firefox_root / "profiles.ini"
        if not profiles_ini.exists():
            logger.debug("Firefox profiles.ini not found: %s", profiles_ini)
            return

        parser = configparser.ConfigParser()
        try:
            parser.read(profiles_ini, encoding="utf-8")
        except configparser.Error as e:
            logger.warning("Failed to parse Firefox profiles.ini: %s", e)
            return

        for section in parser.sections():
            if not section.startswith("Profile"):
                continue

            profile_path = self._resolve_profile_path(parser, section, firefox_root)
            if profile_path is None:
                continue

            cookie_db = profile_path / "cookies.sqlite"
            if not cookie_db.exists():
                logger.debug(
                    "Firefox profile %s has no cookies.sqlite",
                    section,
                )
                continue

            # Use profile folder name as profile_id
            profile_id = profile_path.name

            yield BrowserStore(
                browser_name="Firefox",
                profile_id=profile_id,
                db_path=cookie_db,
                is_chromium=False,
                local_state_path=None,
            )

    def _resolve_profile_path(
        self,
        parser: configparser.ConfigParser,
        section: str,
        firefox_root: Path,
    ) -> Path | None:
        """Resolve profile path from profiles.ini section."""
        if not parser.has_option(section, "Path"):
            logger.debug("Firefox section %s has no Path", section)
            return None

        path_value = parser.get(section, "Path")
        is_relative = parser.getint(section, "IsRelative", fallback=1)

        if is_relative:
            profile_path = firefox_root / path_value
        else:
            profile_path = Path(path_value)

        if not profile_path.exists():
            logger.debug("Firefox profile path does not exist: %s", profile_path)
            return None

        return profile_path
