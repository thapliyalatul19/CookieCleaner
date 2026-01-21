"""Browser profile scanner package."""

from src.scanner.browser_paths import (
    BrowserConfig,
    ALL_BROWSERS,
    CHROMIUM_BROWSERS,
    CHROME_CONFIG,
    EDGE_CONFIG,
    BRAVE_CONFIG,
    OPERA_CONFIG,
    VIVALDI_CONFIG,
    FIREFOX_CONFIG,
)
from src.scanner.chromium_resolver import ChromiumProfileResolver
from src.scanner.firefox_resolver import FirefoxProfileResolver
from src.scanner.profile_resolver import ProfileResolver
from src.scanner.cookie_reader import BaseCookieReader, create_reader
from src.scanner.chromium_cookie_reader import ChromiumCookieReader
from src.scanner.firefox_cookie_reader import FirefoxCookieReader
from src.scanner.db_copy import copy_db_to_temp, cleanup_temp_db

__all__ = [
    # Profile resolvers
    "ProfileResolver",
    "ChromiumProfileResolver",
    "FirefoxProfileResolver",
    # Browser configs
    "BrowserConfig",
    "ALL_BROWSERS",
    "CHROMIUM_BROWSERS",
    "CHROME_CONFIG",
    "EDGE_CONFIG",
    "BRAVE_CONFIG",
    "OPERA_CONFIG",
    "VIVALDI_CONFIG",
    "FIREFOX_CONFIG",
    # Cookie readers
    "BaseCookieReader",
    "ChromiumCookieReader",
    "FirefoxCookieReader",
    "create_reader",
    # Utilities
    "copy_db_to_temp",
    "cleanup_temp_db",
]
